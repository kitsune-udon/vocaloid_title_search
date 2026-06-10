#!/usr/bin/env python3
"""Smoke test a local or deployed Cloudflare Worker API."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout", type=float, default=10.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    health = get_json(f"{base_url}/health", args.timeout)
    assert health == {"ok": True, "database_ready": True}, health

    metadata = get_json(f"{base_url}/api/metadata", args.timeout)
    assert metadata["schema_version"] == "7", metadata

    labels = get_json(f"{base_url}/api/popularity-labels", args.timeout)
    assert labels["labels"], labels

    search = get_json(
        f"{base_url}/api/search?length=7&sort=popularity&page_size=50",
        args.timeout,
    )
    assert search["total"] > 0, search
    assert search["results"], search

    query = urllib.parse.urlencode({"url": "https://w.atwiki.jp/hmiku/pages/82.html"})
    detail = get_json(f"{base_url}/api/song-detail?{query}", args.timeout)
    assert detail["page_title"] == "メルト", detail
    assert "videos" in detail, detail

    stats = get_json(f"{base_url}/api/stats", args.timeout)
    assert stats["total_songs"] > 0, stats

    print(
        json.dumps(
            {
                "ok": True,
                "database_ready": health["database_ready"],
                "song_count": metadata["song_count"],
                "search_total": search["total"],
                "first_result": search["results"][0]["title"],
            },
            ensure_ascii=False,
        )
    )
    return 0


def get_json(url: str, timeout: float):
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "vocaloid-title-search-smoke-test/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"worker smoke test failed: {exc}", file=sys.stderr)
        raise
