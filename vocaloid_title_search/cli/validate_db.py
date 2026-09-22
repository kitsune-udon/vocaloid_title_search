#!/usr/bin/env python3
"""Validate the local Vocaloid song database."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from vocaloid_title_search.cli.common import parser
from vocaloid_title_search.database import DEFAULT_DB_PATH
from vocaloid_title_search.quality_policy import QualityPolicy
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
    arg_parser.add_argument("--require-video-metadata", action="store_true", help="公開用: 両動画サービスの補完記録を必須にします。")
    arg_parser.add_argument("--baseline-db", type=Path, help="比較する前回DB。")
    arg_parser.add_argument("--max-count-drop", type=float, default=0.20)
    arg_parser.add_argument("--max-coverage-drop", type=float, default=0.10)
    arg_parser.add_argument("--min-video-success-rate", type=float, default=0.80)
    args = arg_parser.parse_args(argv)
    try:
        args.policy = QualityPolicy(args.max_count_drop, args.max_coverage_drop, args.min_video_success_rate)
    except ValueError as exc:
        arg_parser.error(str(exc))
    return args


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
    if report.comparison:
        print("comparison:")
        for key, change in report.comparison.items():
            print(f"- {key}: {change}")
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
    report = validate_database_quality(args.db_path, require_video_metadata=args.require_video_metadata,
                                       baseline_path=args.baseline_db, policy=args.policy)
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print_text_report(report)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
