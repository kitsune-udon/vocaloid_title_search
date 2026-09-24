#!/usr/bin/env python3
"""Build the Vocaloid search SQLite database."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import tempfile
import time
import urllib.error
from contextlib import closing
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from vocaloid_title_search.database import (
    DEFAULT_DB_PATH,
    ensure_database,
    DETAIL_SCHEMA_VERSION,
    list_song_urls,
    refresh_detail_metadata,
    rebuild_database,
    save_song_detail,
)
from vocaloid_title_search.cli.common import (
    add_http_options,
    configure_http_from_args,
    parser,
    positive_int,
)
from vocaloid_title_search.detail import fetch_song_detail
from vocaloid_title_search.detail_contract import valid_detail
from vocaloid_title_search.build_checkpoint import build_lock, mark_checkpoint, verify_checkpoint, reuse_details
from vocaloid_title_search.video_metadata import refresh_stored_video_metadata
from vocaloid_title_search.cli.refresh_video_metadata import (
    DEFAULT_VIDEO_METADATA_WORKERS,
    DEFAULT_VIDEO_METADATA_REQUEST_INTERVAL,
)
from vocaloid_title_search.database_quality import validate_database_quality
from vocaloid_title_search.wiki import DEFAULT_TAG_URL, WikiClient, build_title_corpus

DEFAULT_BUILD_WORKERS = 8


def parse_args(argv: list[str]) -> argparse.Namespace:
    arg_parser = parser(
        description="初音ミク Wiki から検索DBと曲詳細を構築します。"
    )
    arg_parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="SQLite DBの保存先。",
    )
    arg_parser.add_argument(
        "--source-url",
        default=DEFAULT_TAG_URL,
        help="取得元URL。",
    )
    arg_parser.add_argument(
        "--workers",
        type=positive_int,
        default=DEFAULT_BUILD_WORKERS,
        help="曲詳細取得時の最大並列数。",
    )
    arg_parser.add_argument(
        "--with-video-metadata", action="store_true",
        help="公開用: 両動画サービスの補完と検査後にDBを差し替えます。",
    )
    arg_parser.add_argument("--resume", action="store_true", help="中断時のDBを保持し、次回は保存済み詳細から再開します。")
    arg_parser.add_argument("--reuse-details-days", type=positive_int, default=0, help="指定日数内の詳細を前回DBから再利用します。省略時は全取得。")
    add_http_options(arg_parser)
    return arg_parser.parse_args(argv)


def configure_fetch_policy(args: argparse.Namespace) -> None:
    configure_http_from_args(args)


def build_database(args: argparse.Namespace) -> int:
    try:
        with build_lock(args.db_path):
            return build_locked(args)
    except (ValueError, sqlite3.DatabaseError, OSError) as exc:
        print(f"DB構築失敗: {exc}", file=sys.stderr)
        return 1


def build_locked(args: argparse.Namespace) -> int:
    configure_fetch_policy(args)
    started_at = time.perf_counter()
    checkpoint = args.db_path.with_name(f".{args.db_path.name}.build.checkpoint.sqlite3")
    continuing = args.resume and checkpoint.exists()
    temp_path = checkpoint if args.resume else temporary_build_database_path(args.db_path)
    try:
        if continuing:
            verify_checkpoint(temp_path, args)
            print("チェックポイントから再開します。", flush=True)
        else:
            client = WikiClient(timeout=args.timeout)
            try:
                raw_songs, popularity_map = build_title_corpus(client, args.source_url,
                    progress=lambda message: print(message, flush=True))
            except (urllib.error.URLError, TimeoutError) as exc:
                print(f"曲一覧の取得に失敗しました: {exc}", file=sys.stderr)
                return 1
            rebuild_database(temp_path, raw_songs, popularity_map, args.source_url)
            mark_checkpoint(temp_path, args)
            reused = reuse_details(args.db_path, temp_path, args.reuse_details_days)
            print(f"登録曲数: {len(raw_songs)} / 詳細再利用: {reused}", flush=True)
        detail_status = build_song_details(args, temp_path)
        if detail_status:
            return detail_status
        if args.with_video_metadata:
            video_args = argparse.Namespace(**vars(args))
            video_args.request_interval = DEFAULT_VIDEO_METADATA_REQUEST_INTERVAL
            configure_http_from_args(video_args)
            metadata_status = refresh_stored_video_metadata(
                temp_path, max_workers=DEFAULT_VIDEO_METADATA_WORKERS, timeout=args.timeout,
                progress=lambda message: print(message, flush=True), previous_db_path=args.db_path,
            )
            if metadata_status:
                return metadata_status
        report = validate_database_quality(temp_path, require_video_metadata=args.with_video_metadata,
                                           baseline_path=args.db_path if args.db_path.exists() else None)
        if not report.ok:
            print("DB品質検査失敗: " + "; ".join(report.errors), file=sys.stderr)
            return 1
        publish_build_database(temp_path, args.db_path, preserve_checkpoint=args.resume)
        print(f"DBを作成しました: {args.db_path} / {time.perf_counter() - started_at:.1f}秒")
        return 0
    finally:
        if not args.resume:
            temp_path.unlink(missing_ok=True)


def publish_build_database(candidate: Path, target: Path, *, preserve_checkpoint: bool) -> None:
    # Keep the resumable candidate intact until the final rename has succeeded.
    output = temporary_build_database_path(target) if preserve_checkpoint else candidate
    try:
        if preserve_checkpoint:
            with closing(sqlite3.connect(candidate)) as source, closing(sqlite3.connect(output)) as destination:
                source.backup(destination)
        with closing(sqlite3.connect(output)) as connection:
            connection.execute("DELETE FROM metadata WHERE key = 'build_checkpoint'")
            connection.commit()
        os.replace(output, target)
        if preserve_checkpoint:
            candidate.unlink(missing_ok=True)
    finally:
        if preserve_checkpoint:
            output.unlink(missing_ok=True)


def temporary_build_database_path(db_path: Path) -> Path:
    handle = tempfile.NamedTemporaryFile(
        prefix=f".{db_path.name}.build.",
        suffix=".sqlite3",
        dir=db_path.parent,
        delete=False,
    )
    handle.close()
    return Path(handle.name)


def build_song_details(args: argparse.Namespace, db_path: Path) -> int:
    urls = list_song_urls(db_path)
    completed = 0
    with closing(sqlite3.connect(db_path)) as existing:
        stored = set()
        for url, payload, schema in existing.execute("SELECT url, payload_json, schema_version FROM song_details"):
            try:
                detail = json.loads(payload)
                if (schema == DETAIL_SCHEMA_VERSION and isinstance(detail, dict)
                        and valid_detail(detail, url, complete=args.with_video_metadata)):
                    stored.add(url)
            except json.JSONDecodeError:
                pass
    pending_urls = [url for url in urls if url not in stored]
    started_at = time.perf_counter()
    print(f"曲詳細取得中: {len(urls)}件", flush=True)
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        ensure_database(connection)
        for attempt in range(1, 4):
            failed_urls: list[str] = []
            if attempt > 1:
                print(f"曲詳細リトライ {attempt - 1}: {len(pending_urls)}件", flush=True)
            with ThreadPoolExecutor(max_workers=args.workers) as executor:
                future_to_url = {
                    executor.submit(
                        fetch_song_detail,
                        url,
                        timeout=args.timeout,
                    ): url
                    for url in pending_urls
                }
                for future in as_completed(future_to_url):
                    url = future_to_url[future]
                    try:
                        detail = future.result()
                        save_song_detail(
                            connection,
                            url,
                            detail,
                            datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        )
                        completed += 1
                        if completed % 20 == 0:
                            connection.commit()
                            elapsed = time.perf_counter() - started_at
                            print(
                                f"曲詳細進捗: {completed}/{len(urls)}件 "
                                f"({completed / elapsed:.2f}件/秒)",
                                flush=True,
                            )
                    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
                        failed_urls.append(url)
                        print(f"詳細取得に失敗しました: {url} {exc}", file=sys.stderr)
            connection.commit()
            pending_urls = failed_urls
            if not pending_urls:
                break
        refresh_detail_metadata(connection)
        connection.commit()

    failed = len(pending_urls)
    print(f"曲詳細を保存しました: 成功 {completed} / 失敗 {failed} / {time.perf_counter() - started_at:.1f}秒")
    return 0 if failed == 0 else 1


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    return build_database(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
