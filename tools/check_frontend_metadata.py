#!/usr/bin/env python3
"""Validate frontend metadata that protects the personal-operation policy."""

from __future__ import annotations

import argparse
from pathlib import Path


REQUIRED_ROBOTS_CONTENT = "noindex,nofollow,noarchive"
REQUIRED_STATIC_HEADERS = (
    "X-Content-Type-Options: nosniff",
    "Referrer-Policy: no-referrer",
    "Permissions-Policy: camera=(), microphone=(), geolocation=()",
)
FORBIDDEN_METADATA_MARKERS = (
    'property="og:',
    "property='og:",
    'name="twitter:',
    "name='twitter:",
    'type="application/ld+json"',
    "type='application/ld+json'",
)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise SystemExit(f"missing required file: {path}") from exc


def check_index_html(path: Path) -> list[str]:
    html = read_text(path)
    errors: list[str] = []

    if REQUIRED_ROBOTS_CONTENT not in html:
        errors.append(
            f"{path}: missing robots meta content {REQUIRED_ROBOTS_CONTENT!r}"
        )

    for marker in FORBIDDEN_METADATA_MARKERS:
        if marker in html:
            errors.append(
                f"{path}: forbidden search/social discovery metadata marker {marker!r}"
            )

    return errors


def check_robots_txt(path: Path) -> list[str]:
    text = read_text(path)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    errors: list[str] = []

    if "User-agent: *" not in lines:
        errors.append(f"{path}: missing 'User-agent: *'")
    if "Disallow: /" not in lines:
        errors.append(f"{path}: missing 'Disallow: /'")

    return errors


def check_static_headers(path: Path) -> list[str]:
    text = read_text(path)
    errors: list[str] = []
    for header in REQUIRED_STATIC_HEADERS:
        if header not in text:
            errors.append(f"{path}: missing static header {header!r}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()

    root = args.root
    errors = [
        *check_index_html(root / "frontend" / "index.html"),
        *check_robots_txt(root / "frontend" / "public" / "robots.txt"),
        *check_static_headers(root / "frontend" / "public" / "_headers"),
    ]

    if errors:
        for error in errors:
            print(error)
        return 1

    print("Frontend metadata policy check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
