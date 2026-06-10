#!/usr/bin/env python3
"""Check that API contract sources stay tied to shared types."""

from __future__ import annotations

import argparse
from pathlib import Path


EXPECTED_MARKERS = {
    "shared/api-types.ts": (
        "export interface SearchResponse",
        "export interface SongDetail",
        "export interface StatisticsResponse",
        "export interface ErrorResponse",
    ),
    "frontend/src/types.ts": (
        'from "../../shared/api-types"',
    ),
    "frontend/src/api.ts": (
        'from "./types"',
    ),
    "cloudflare/worker/src/index.ts": (
        'from "../../../shared/api-types"',
    ),
    "docs/web-api.md": (
        "shared/api-types.ts",
        "cloudflare/worker/src/index.ts",
        "frontend/src/api.ts",
    ),
}


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise SystemExit(f"missing required file: {path}") from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()

    errors: list[str] = []
    for relative_path, markers in EXPECTED_MARKERS.items():
        path = args.root / relative_path
        text = read_text(path)
        for marker in markers:
            if marker not in text:
                errors.append(f"{relative_path}: missing API contract marker {marker!r}")

    if errors:
        for error in errors:
            print(error)
        return 1

    print("API contract source check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
