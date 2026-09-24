#!/usr/bin/env python3
"""Measure representative Worker API response times."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
import urllib.error
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
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--redact-base-url", action="store_true")
    parser.add_argument("--interval", type=float, default=0.2)
    parser.add_argument("--max-p95-ms", type=float, default=0, help="0 disables the latency gate; errors always fail.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.repeat < 1:
        raise SystemExit("--repeat must be 1 or greater")

    if not math.isfinite(args.timeout) or args.timeout <= 0 or not math.isfinite(args.interval) or args.interval < 0 or not math.isfinite(args.max_p95_ms) or args.max_p95_ms < 0:
        raise SystemExit("timeout must be positive; interval and max-p95-ms must be nonnegative and finite")
    base_url = args.base_url.rstrip("/")
    validate_target(base_url, args.repeat)
    results = []
    for request in representative_requests():
        result = measure_request(base_url, request, timeout=args.timeout, repeat=args.repeat, interval=args.interval)
        results.append(result)
        if result["errors"]:
            break
    report = {"base_url": "configured" if args.redact_base_url else base_url,
              "measured_at": datetime.now(timezone.utc).isoformat(), "repeat": args.repeat, "results": results}
    encoded = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n")
    if args.json:
        print(encoded)
    else:
        print_text_report(report["base_url"], args.repeat, results)
    return int(any(result["errors"] or (args.max_p95_ms and result["p95_ms"] > args.max_p95_ms) for result in results))


def validate_target(base_url: str, repeat: int) -> None:
    url = urllib.parse.urlsplit(base_url)
    if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password:
        raise SystemExit("base-url must be an HTTP(S) URL without credentials")
    if repeat > 1 and url.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise SystemExit("Public API profiling is limited to --repeat 1; repeat performance tests on local D1")


def measure_request(
    base_url: str,
    request: ProfileRequest,
    *,
    timeout: float,
    repeat: int,
    interval: float = 0,
) -> dict[str, object]:
    durations: list[float] = []
    status = 0
    bytes_read = 0
    errors = 0
    statuses: dict[str, int] = {}
    rows_read: list[int | None] = []
    for attempt in range(repeat):
        if attempt and interval:
            time.sleep(interval)
        row_count = None
        started_at = time.perf_counter()
        try:
            status, bytes_read, row_count = fetch_once(f"{base_url}{request.path}", timeout)
        except urllib.error.HTTPError as exc:
            status, bytes_read = exc.code, 0
            exc.close()
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            status, bytes_read = 0, 0
        errors += int(status != 200)
        statuses[str(status)] = statuses.get(str(status), 0) + 1
        durations.append((time.perf_counter() - started_at) * 1000)
        rows_read.append(row_count)
        if status != 200:
            break
    return {
        "name": request.name,
        "path": request.path,
        "status": status,
        "bytes": bytes_read,
        "min_ms": round(min(durations), 2),
        "median_ms": round(statistics.median(durations), 2),
        "max_ms": round(max(durations), 2),
        "p95_ms": round(sorted(durations)[math.ceil(len(durations) * 0.95) - 1], 2),
        "errors": errors,
        "samples": len(durations),
        "rows_read": rows_read,
        "total_rows_read": sum(rows_read) if all(value is not None for value in rows_read) else None,
        "error_rate": errors / len(durations),
        "statuses": statuses,
    }


def fetch_once(url: str, timeout: float) -> tuple[int, int, int | None]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "vocaloid-title-search-api-profiler/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read()
        if urllib.parse.urlsplit(url).path == "/health":
            health = json.loads(body)
            if not isinstance(health, dict) or health.get("database_ready") is not True:
                raise urllib.error.URLError("database is not ready; profiling stopped")
        measured = response.headers.get("x-d1-rows-read", "")
        return response.status, len(body), int(measured) if measured.isdecimal() else None


def print_text_report(base_url: str, repeat: int, results: list[dict[str, object]]) -> None:
    print(f"Worker API profile: {base_url} repeat={repeat}")
    print("name\tstatus\tbytes\tmin_ms\tmedian_ms\tp95_ms\terror_rate\trows_read")
    for result in results:
        print(
            f"{result['name']}\t{result['status']}\t{result['bytes']}\t"
            f"{result['min_ms']}\t{result['median_ms']}\t{result['p95_ms']}\t{result['error_rate']:.1%}\t{result['total_rows_read']}"
        )


if __name__ == "__main__":
    raise SystemExit(main())
