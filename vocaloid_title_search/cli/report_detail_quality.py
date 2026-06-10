#!/usr/bin/env python3
"""Report likely detail extraction gaps in the local database."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from vocaloid_title_search.cli.common import non_negative_int, parser
from vocaloid_title_search.database import DEFAULT_DB_PATH
from vocaloid_title_search.detail_quality import DetailQualityReport, report_detail_quality


def parse_args(argv: list[str]) -> argparse.Namespace:
    arg_parser = parser(
        description="保存済み曲詳細JSONを読み、基本情報・紹介文・動画・公開年の欠損候補を一覧化します。"
    )
    arg_parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="検査するSQLite DBのパス。",
    )
    arg_parser.add_argument(
        "--limit",
        type=non_negative_int,
        default=100,
        help="表示する曲数。0なら件数だけ表示します。",
    )
    arg_parser.add_argument(
        "--json",
        action="store_true",
        help="レポートをJSONで出力します。",
    )
    return arg_parser.parse_args(argv)


def print_text_report(report: DetailQualityReport) -> None:
    print("Detail extraction quality report")
    print(f"DB: {report.db_path}")
    print(f"total_details: {report.total_details}")
    print(f"total_issues: {report.total_issues}")
    print("issue_counts:")
    for key in sorted(report.issue_counts):
        print(f"- {key}: {report.issue_counts[key]}")
    if report.issues:
        print("issues:")
        for issue in report.issues:
            print(f"- {issue.title}\t{issue.url}\t{', '.join(issue.checks)}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if not args.db_path.exists():
        print(f"DBが見つかりません: {args.db_path}", file=sys.stderr)
        return 2
    report = report_detail_quality(
        args.db_path,
        limit=None if args.limit is None else args.limit,
    )
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print_text_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
