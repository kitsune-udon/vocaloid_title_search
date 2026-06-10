#!/usr/bin/env python3
"""Validate the local Vocaloid song database."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from vocaloid_title_search.cli.common import parser
from vocaloid_title_search.database import DEFAULT_DB_PATH
from vocaloid_title_search.database_quality import (
    DatabaseQualityReport,
    validate_database_quality,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    arg_parser = parser(
        description="ローカルSQLite DBの件数、metadata、詳細JSON、派生テーブルの整合性を検査します。"
    )
    arg_parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="検査するSQLite DBのパス。",
    )
    arg_parser.add_argument(
        "--json",
        action="store_true",
        help="検査結果をJSONで出力します。",
    )
    return arg_parser.parse_args(argv)


def print_text_report(report: DatabaseQualityReport) -> None:
    status = "OK" if report.ok else "FAIL"
    print(f"{status} database quality check")
    print(f"DB: {report.db_path}")
    if report.errors:
        print("errors:")
        for error in report.errors:
            print(f"- {error}")
    if report.warnings:
        print("warnings:")
        for warning in report.warnings:
            print(f"- {warning}")
    if report.counts:
        print("counts:")
        for key in sorted(report.counts):
            print(f"- {key}: {report.counts[key]}")
    if report.metadata:
        print("metadata:")
        for key in sorted(report.metadata):
            print(f"- {key}: {report.metadata[key]}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    report = validate_database_quality(args.db_path)
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print_text_report(report)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
