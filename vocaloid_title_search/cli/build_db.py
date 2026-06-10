#!/usr/bin/env python3
"""Build the Vocaloid search SQLite database."""

from __future__ import annotations

import argparse
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
    add_http_options(arg_parser)
    return arg_parser.parse_args(argv)


def configure_fetch_policy(args: argparse.Namespace) -> None:
    configure_http_from_args(args)


def build_database(args: argparse.Namespace) -> int:
    configure_fetch_policy(args)
    client = WikiClient(timeout=args.timeout)
    started_at = time.perf_counter()
    try:
        raw_songs, popularity_map = build_title_corpus(
            client,
            args.source_url,
            progress=lambda message: print(message, flush=True),
        )
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"曲一覧の取得に失敗しました: {exc}", file=sys.stderr)
        return 1
    corpus_elapsed = time.perf_counter() - started_at
    print(f"曲一覧取得完了: {corpus_elapsed:.1f}秒", flush=True)

    args.db_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = temporary_build_database_path(args.db_path)
    try:
        write_started_at = time.perf_counter()
        print("DB書き込み中", flush=True)
        rebuild_database(temp_path, raw_songs, popularity_map, args.source_url)
        print(f"登録曲数: {len(raw_songs)}")
        print(f"曲一覧DB書き込み完了: {time.perf_counter() - write_started_at:.1f}秒", flush=True)
        detail_status = build_song_details(args, temp_path)
        if detail_status:
            return detail_status
        os.replace(temp_path, args.db_path)
        print(f"DBを作成しました: {args.db_path}")
        print(f"総経過時間: {time.perf_counter() - started_at:.1f}秒", flush=True)
        return 0
    finally:
        if temp_path.exists():
            temp_path.unlink()


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
    pending_urls = urls
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
                        if completed % 100 == 0:
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
