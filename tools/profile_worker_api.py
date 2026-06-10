#!/usr/bin/env python3
"""Measure representative Worker API response times."""

from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class ProfileRequest:
    name: str
    path: str


def representative_requests() -> list[ProfileRequest]:
    detail_query = urllib.parse.urlencode({"url": "https://w.atwiki.jp/hmiku/pages/82.html"})
    return [
        ProfileRequest("health", "/health"),
        ProfileRequest("metadata", "/api/metadata"),
        ProfileRequest("stats", "/api/stats"),
        ProfileRequest("search_length", "/api/search?length=7&sort=popularity&page_size=50"),
        ProfileRequest("search_composer", "/api/search?composer=ryo&sort=popularity&page_size=50"),
        ProfileRequest("search_year", "/api/search?year=2021&sort=published_year_desc&page_size=50"),
        ProfileRequest(
            "search_tag",
            "/api/search?popularity_label=%E3%83%9F%E3%83%AA%E3%82%AA%E3%83%B3%E9%81%94%E6%88%90%E6%9B%B2&sort=popularity&page_size=50",
        ),
        ProfileRequest("search_page_size_200", "/api/search?sort=popularity&page_size=200"),
        ProfileRequest("song_detail", f"/api/song-detail?{detail_query}"),
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.repeat < 1:
        raise SystemExit("--repeat must be 1 or greater")

    base_url = args.base_url.rstrip("/")
    results = [
        measure_request(base_url, request, timeout=args.timeout, repeat=args.repeat)
        for request in representative_requests()
    ]
    if args.json:
        print(json.dumps({"base_url": base_url, "repeat": args.repeat, "results": results}, ensure_ascii=False, indent=2))
    else:
        print_text_report(base_url, args.repeat, results)
    return 0


def measure_request(
    base_url: str,
    request: ProfileRequest,
    *,
    timeout: float,
    repeat: int,
) -> dict[str, object]:
    durations: list[float] = []
    status = 0
    bytes_read = 0
    for _ in range(repeat):
        started_at = time.perf_counter()
        status, bytes_read = fetch_once(f"{base_url}{request.path}", timeout)
        durations.append((time.perf_counter() - started_at) * 1000)
    return {
        "name": request.name,
        "path": request.path,
        "status": status,
        "bytes": bytes_read,
        "min_ms": round(min(durations), 2),
        "median_ms": round(statistics.median(durations), 2),
        "max_ms": round(max(durations), 2),
    }


def fetch_once(url: str, timeout: float) -> tuple[int, int]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "vocaloid-title-search-api-profiler/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read()
        return response.status, len(body)


def print_text_report(base_url: str, repeat: int, results: list[dict[str, object]]) -> None:
    print(f"Worker API profile: {base_url} repeat={repeat}")
    print("name\tstatus\tbytes\tmin_ms\tmedian_ms\tmax_ms")
    for result in results:
        print(
            f"{result['name']}\t{result['status']}\t{result['bytes']}\t"
            f"{result['min_ms']}\t{result['median_ms']}\t{result['max_ms']}"
        )


if __name__ == "__main__":
    raise SystemExit(main())
