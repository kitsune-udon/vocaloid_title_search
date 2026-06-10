#!/usr/bin/env python3
"""Search stored Vocaloid song titles by counted title length."""

from __future__ import annotations

import argparse
import os
import signal
import sys
from pathlib import Path

from vocaloid_title_search.cli.common import non_negative_int, parser
from vocaloid_title_search.database import (
    DEFAULT_DB_PATH,
    POPULARITY_ORDER,
    PUBLISHED_YEAR_ASC_ORDER,
    PUBLISHED_YEAR_DESC_ORDER,
    TITLE_LENGTH_ASC_ORDER,
    TITLE_LENGTH_DESC_ORDER,
    load_titles_by_length,
)
from vocaloid_title_search.models import SearchResult


def parse_args(argv: list[str]) -> argparse.Namespace:
    arg_parser = parser(
        description="作成済みDBから、空白を除いてN文字の有名ボカロ曲タイトルを検索します。"
    )
    arg_parser.add_argument(
        "n",
        type=non_negative_int,
        help="検索したいタイトル文字数。記号は1文字として数え、空白は数えません。",
    )
    arg_parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="SQLite DBの保存先。",
    )
    arg_parser.add_argument(
        "--show-count",
        action="store_true",
        help="タイトルの後ろに文字数も表示します。",
    )
    arg_parser.add_argument(
        "--show-artist",
        action="store_true",
        help="タイトルの後ろに作曲者も表示します。",
    )
    arg_parser.add_argument(
        "--show-artist-note",
        action="store_true",
        help="タイトルの後ろに作曲者補足も表示します。",
    )
    arg_parser.add_argument(
        "--show-url",
        action="store_true",
        help="タイトルの後ろに曲ページURLも表示します。",
    )
    arg_parser.add_argument(
        "--show-popularity",
        action="store_true",
        help="タイトルの後ろに人気度スコアと根拠タグも表示します。",
    )
    arg_parser.add_argument(
        "--show-year",
        action="store_true",
        help="タイトルの後ろに公開年も表示します。",
    )
    arg_parser.add_argument(
        "--sort",
        choices=(
            POPULARITY_ORDER,
            TITLE_LENGTH_ASC_ORDER,
            TITLE_LENGTH_DESC_ORDER,
            PUBLISHED_YEAR_ASC_ORDER,
            PUBLISHED_YEAR_DESC_ORDER,
        ),
        default=POPULARITY_ORDER,
        help="並び順。",
    )
    return arg_parser.parse_args(argv)


def validate_args(args: argparse.Namespace) -> int:
    if not args.db_path.exists():
        print(f"DBが見つかりません: {args.db_path}", file=sys.stderr)
        print(
            "先に uv run --cache-dir .uv-cache python -m vocaloid_title_search.cli.build_db を実行してください。",
            file=sys.stderr,
        )
        return 1
    return 0


def search_titles(args: argparse.Namespace) -> list[SearchResult]:
    return load_titles_by_length(args.db_path, args.n, args.sort)


def print_results(results: list[SearchResult], args: argparse.Namespace) -> None:
    for result in results:
        print(format_result(result, args))


def format_result(result: SearchResult, args: argparse.Namespace) -> str:
    fields = [result.title]
    if args.show_count:
        fields.append(str(result.title_length))
    if args.show_artist:
        fields.append(result.artist)
    if args.show_artist_note:
        fields.append(result.artist_note)
    if args.show_url:
        fields.append(result.url)
    if args.show_popularity:
        fields.append(str(result.popularity_score))
        fields.append(result.popularity_label)
    if args.show_year:
        fields.append(str(result.published_year) if result.published_year is not None else "")
    return "	".join(fields)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    validation_status = validate_args(args)
    if validation_status:
        return validation_status
    print_results(search_titles(args), args)
    return 0


if __name__ == "__main__":
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    try:
        raise SystemExit(main(sys.argv[1:]))
    except BrokenPipeError:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
        raise SystemExit(1)
