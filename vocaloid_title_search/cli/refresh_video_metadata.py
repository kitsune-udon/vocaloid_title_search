#!/usr/bin/env python3
"""Refresh video metadata stored in the Vocaloid search database."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from vocaloid_title_search.cli.common import (
    add_http_options,
    configure_http_from_args,
    parser,
    positive_int,
)
from vocaloid_title_search.database import DEFAULT_DB_PATH
from vocaloid_title_search.video_metadata import refresh_stored_video_metadata

DEFAULT_VIDEO_METADATA_WORKERS = 32
DEFAULT_VIDEO_METADATA_REQUEST_INTERVAL = 0.0


def parse_args(argv: list[str]) -> argparse.Namespace:
    arg_parser = parser(
        description="既存DB内の動画IDを使い、動画タイトルとサムネイルURLを更新します。"
    )
    arg_parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="SQLite DBの保存先。",
    )
    arg_parser.add_argument(
        "--workers",
        type=positive_int,
        default=DEFAULT_VIDEO_METADATA_WORKERS,
        help="動画メタデータ取得時の最大並列数。",
    )
    add_http_options(
        arg_parser,
        request_interval_default=DEFAULT_VIDEO_METADATA_REQUEST_INTERVAL,
    )
    return arg_parser.parse_args(argv)


def configure_fetch_policy(args: argparse.Namespace) -> None:
    configure_http_from_args(args)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    configure_fetch_policy(args)
    return refresh_stored_video_metadata(
        args.db_path,
        max_workers=args.workers,
        timeout=args.timeout,
        progress=lambda message: print(message, flush=True),
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
