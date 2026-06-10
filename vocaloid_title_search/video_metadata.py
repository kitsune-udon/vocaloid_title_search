"""Video metadata refresh helpers for stored song details."""

from __future__ import annotations

import json
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import closing
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Callable, Iterator

from vocaloid_title_search.database import ensure_database, load_song_detail_payloads
from vocaloid_title_search.detail import (
    clean_text,
    fallback_niconico_thumbnail_url,
    fallback_niconico_thumbnail_urls,
    fallback_youtube_thumbnail_urls,
)
from vocaloid_title_search.http import fetch_text as http_fetch_text

VideoMetadata = dict[str, dict[str, str]]
VideoMetadataByService = dict[str, VideoMetadata]
ProgressCallback = Callable[[str], None]
USER_AGENT = "vocaloid-title-search/1.0"


def fetch_text(url: str, timeout: float = 10.0) -> str:
    return http_fetch_text(url, timeout=timeout, user_agent=USER_AGENT)


def refresh_stored_video_metadata(
    db_path: Path,
    *,
    max_workers: int,
    timeout: float,
    progress: ProgressCallback | None = None,
) -> int:
    started_at = time.perf_counter()
    try:
        detail_rows = load_song_detail_payloads(db_path)
    except sqlite3.DatabaseError as exc:
        print(f"DBの読み込みに失敗しました: {exc}", file=sys.stderr)
        return 1
    if not detail_rows:
        print("曲詳細がDBにありません。先にDBを構築してください。", file=sys.stderr)
        return 1

    collect_started_at = time.perf_counter()
    video_ids = collect_video_ids(detail_rows)
    emit(
        progress,
        "動画ID収集完了: "
        f"ニコニコ {len(video_ids['niconico'])}件 / "
        f"YouTube {len(video_ids['youtube'])}件 / "
        f"{time.perf_counter() - collect_started_at:.1f}秒",
    )

    metadata = fetch_all_video_metadata(
        video_ids,
        max_workers=max_workers,
        timeout=timeout,
        started_at=time.perf_counter(),
        progress=progress,
    )
    summary = summarize_video_metadata(video_ids, metadata)
    emit(
        progress,
        "動画メタデータ取得結果: "
        f"対象 {summary['total']}件 / "
        f"成功 {summary['success']}件 / "
        f"失敗 {summary['failure']}件 / "
        f"フォールバック {summary['fallback']}件",
    )
    write_started_at = time.perf_counter()
    updated_entries = write_video_metadata(db_path, detail_rows, metadata)
    emit(
        progress,
        f"動画メタデータ書き込み完了: {updated_entries}件 / "
        f"{time.perf_counter() - write_started_at:.1f}秒",
    )
    emit(progress, f"動画メタデータ更新完了: {time.perf_counter() - started_at:.1f}秒")
    return 0


def summarize_video_metadata(
    video_ids: dict[str, list[str]],
    metadata: VideoMetadataByService,
) -> dict[str, int]:
    total = sum(len(ids) for ids in video_ids.values())
    fetched = sum(len(items) for items in metadata.values())
    fallback = sum(
        1
        for service, items in metadata.items()
        for video_id, item in items.items()
        if is_fallback_metadata(service, video_id, item)
    )
    return {
        "total": total,
        "success": max(fetched - fallback, 0),
        "failure": max(total - fetched, 0),
        "fallback": fallback,
    }


def is_fallback_metadata(service: str, video_id: str, item: dict[str, str]) -> bool:
    if service == "niconico":
        return (
            item.get("title") == "ニコニコ動画"
            or item.get("thumbnail_url") == fallback_niconico_thumbnail_url(video_id)
        )
    if service == "youtube":
        quoted_id = urllib.parse.quote(video_id)
        return (
            item.get("title") == "YouTube"
            or item.get("thumbnail_url") == f"https://img.youtube.com/vi/{quoted_id}/mqdefault.jpg"
        )
    return False


def collect_video_ids(detail_rows: list[tuple[str, dict[str, object]]]) -> dict[str, list[str]]:
    collected: dict[str, set[str]] = {"niconico": set(), "youtube": set()}
    for _, detail in detail_rows:
        for service, video in iter_detail_videos(detail):
            video_id = video.get("id")
            if isinstance(video_id, str) and video_id:
                collected[service].add(video_id)
    return {
        "niconico": sorted(collected["niconico"]),
        "youtube": sorted(collected["youtube"]),
    }


def iter_detail_videos(detail: dict[str, object]) -> Iterator[tuple[str, dict[str, object]]]:
    for section_name in ("videos", "related_videos"):
        section = detail.get(section_name)
        if not isinstance(section, dict):
            continue
        for service in ("niconico", "youtube"):
            videos = section.get(service)
            if not isinstance(videos, list):
                continue
            for video in videos:
                if isinstance(video, dict):
                    yield service, video


def fetch_all_video_metadata(
    video_ids: dict[str, list[str]],
    *,
    max_workers: int,
    timeout: float,
    started_at: float,
    progress: ProgressCallback | None = None,
) -> VideoMetadataByService:
    return {
        "niconico": fetch_service_video_metadata(
            "niconico",
            video_ids["niconico"],
            lambda video_id: niconico_video_metadata(video_id, timeout=timeout),
            max_workers=max_workers,
            started_at=started_at,
            progress=progress,
        ),
        "youtube": fetch_service_video_metadata(
            "youtube",
            video_ids["youtube"],
            lambda video_id: youtube_video_metadata(video_id, timeout=timeout),
            max_workers=max_workers,
            started_at=started_at,
            progress=progress,
        ),
    }


def fetch_service_video_metadata(
    service: str,
    video_ids: list[str],
    fetcher: Callable[[str], dict[str, str]],
    *,
    max_workers: int,
    started_at: float,
    progress: ProgressCallback | None = None,
) -> VideoMetadata:
    metadata: VideoMetadata = {}
    failures = 0
    if not video_ids:
        return metadata
    emit(progress, f"{service}メタデータ取得中: {len(video_ids)}件")
    with ThreadPoolExecutor(max_workers=min(max_workers, len(video_ids))) as executor:
        future_to_video_id = {
            executor.submit(fetcher, video_id): video_id
            for video_id in video_ids
        }
        for completed, future in enumerate(as_completed(future_to_video_id), start=1):
            video_id = future_to_video_id[future]
            try:
                metadata[video_id] = future.result()
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
                failures += 1
                print(f"{service}メタデータ取得に失敗しました: {video_id} {exc}", file=sys.stderr)
            if completed % 500 == 0 or completed == len(video_ids):
                elapsed = time.perf_counter() - started_at
                emit(
                    progress,
                    f"{service}メタデータ進捗: {completed}/{len(video_ids)}件 "
                    f"({completed / elapsed:.2f}件/秒, 失敗 {failures})",
                )
    return metadata


def write_video_metadata(
    db_path: Path,
    detail_rows: list[tuple[str, dict[str, object]]],
    metadata: VideoMetadataByService,
) -> int:
    fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    updated_entries = 0
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        ensure_database(connection)
        for url, detail in detail_rows:
            updated_entries += apply_video_metadata(detail, metadata)
            connection.execute(
                """
                UPDATE song_details
                SET payload_json = ?, fetched_at = ?
                WHERE url = ?
                """,
                (
                    json.dumps(detail, ensure_ascii=False, separators=(",", ":")),
                    fetched_at,
                    url,
                ),
            )
        connection.commit()
    return updated_entries


def apply_video_metadata(
    detail: dict[str, object],
    metadata: VideoMetadataByService,
) -> int:
    updated = 0
    for service, video in iter_detail_videos(detail):
        video_id = video.get("id")
        if not isinstance(video_id, str) or not video_id:
            continue
        item = metadata[service].get(video_id)
        if not item:
            continue
        if service == "niconico":
            thumbnail_urls = unique_strings(
                [item["thumbnail_url"], *fallback_niconico_thumbnail_urls(video_id)]
            )
        else:
            thumbnail_urls = unique_strings(
                [item["thumbnail_url"], *fallback_youtube_thumbnail_urls(video_id)]
            )
        video["title"] = item["title"]
        video["thumbnail_url"] = thumbnail_urls[0]
        video["thumbnail_urls"] = thumbnail_urls
        updated += 1
    return updated


def unique_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


@lru_cache(maxsize=512)
def niconico_video_metadata(video_id: str, *, timeout: float = 10.0) -> dict[str, str]:
    try:
        page_xml = fetch_text(
            f"https://ext.nicovideo.jp/api/getthumbinfo/{urllib.parse.quote(video_id)}",
            timeout=timeout,
        )
        root = ET.fromstring(page_xml)
    except (ET.ParseError, OSError, TimeoutError):
        return {
            "title": "ニコニコ動画",
            "thumbnail_url": fallback_niconico_thumbnail_url(video_id),
        }

    title = clean_text(root.findtext(".//title") or "")
    thumbnail_url = root.findtext(".//thumbnail_url")
    return {
        "title": title or "ニコニコ動画",
        "thumbnail_url": thumbnail_url or fallback_niconico_thumbnail_url(video_id),
    }


@lru_cache(maxsize=512)
def youtube_video_metadata(video_id: str, *, timeout: float = 10.0) -> dict[str, str]:
    fallback_urls = fallback_youtube_thumbnail_urls(video_id)
    fallback = {
        "title": "YouTube",
        "thumbnail_url": fallback_urls[2],
    }
    query = urllib.parse.urlencode(
        {"url": f"https://www.youtube.com/watch?v={video_id}", "format": "json"}
    )
    try:
        payload = json.loads(fetch_text(f"https://www.youtube.com/oembed?{query}", timeout=timeout))
    except (json.JSONDecodeError, OSError, TimeoutError):
        return fallback
    if not isinstance(payload, dict):
        return fallback

    title = payload.get("title")
    thumbnail_url = payload.get("thumbnail_url")
    return {
        "title": clean_text(title) if isinstance(title, str) and clean_text(title) else fallback["title"],
        "thumbnail_url": thumbnail_url if isinstance(thumbnail_url, str) and thumbnail_url else fallback["thumbnail_url"],
    }


def emit(progress: ProgressCallback | None, message: str) -> None:
    if progress is None:
        return
    progress(message)
