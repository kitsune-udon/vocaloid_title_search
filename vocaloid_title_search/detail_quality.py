"""Detail extraction quality reports for stored song details."""

from __future__ import annotations

import json
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from vocaloid_title_search.database import connect_readonly


CHECKS = (
    "invalid_json",
    "missing_credits",
    "missing_composer",
    "suspicious_composer",
    "missing_introduction",
    "missing_primary_videos",
    "missing_published_year",
    "suspicious_published_year",
    "published_year_mismatch",
)

SUSPICIOUS_CREDIT_TOKENS = (
    "http",
    "twitter",
    "x.com",
    "instagram",
    "youtube",
    "homepage",
    "ホームページ",
    "公式サイト",
)


@dataclass(frozen=True)
class DetailQualityIssue:
    title: str
    url: str
    checks: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "title": self.title,
            "url": self.url,
            "checks": self.checks,
        }


@dataclass(frozen=True)
class DetailQualityReport:
    db_path: Path
    total_details: int
    total_issue_rows: int = 0
    issue_counts: dict[str, int] = field(default_factory=dict)
    issues: list[DetailQualityIssue] = field(default_factory=list)

    @property
    def total_issues(self) -> int:
        return self.total_issue_rows

    def to_dict(self) -> dict[str, Any]:
        return {
            "db_path": str(self.db_path),
            "total_details": self.total_details,
            "total_issues": self.total_issues,
            "issue_counts": self.issue_counts,
            "issues": [issue.to_dict() for issue in self.issues],
        }


def report_detail_quality(db_path: Path, *, limit: int | None = 100) -> DetailQualityReport:
    issue_counts = {check: 0 for check in CHECKS}
    issues: list[DetailQualityIssue] = []
    total_details = 0
    total_issue_rows = 0
    with closing(connect_readonly(db_path)) as connection:
        rows = connection.execute(
            """
            SELECT songs.title, songs.song_url, song_details.payload_json, song_details.published_year
            FROM songs
            JOIN song_details ON song_details.url = songs.song_url
            ORDER BY songs.popularity_score DESC, songs.popularity_order, songs.sort_order
            """
        )
        for title, url, payload_json, stored_year in rows:
            total_details += 1
            checks = detail_issue_checks(payload_json, stored_year)
            if not checks:
                continue
            total_issue_rows += 1
            for check in checks:
                issue_counts[check] += 1
            if limit is None or len(issues) < limit:
                issues.append(DetailQualityIssue(title=title, url=url, checks=checks))
    return DetailQualityReport(
        db_path=db_path,
        total_details=total_details,
        total_issue_rows=total_issue_rows,
        issue_counts=issue_counts,
        issues=issues,
    )


def detail_issue_checks(payload_json: str, stored_year: int | None) -> list[str]:
    try:
        detail = json.loads(payload_json)
    except json.JSONDecodeError:
        return ["invalid_json"]

    checks: list[str] = []
    credits = detail.get("credits")
    if not isinstance(credits, dict) or not credits:
        checks.append("missing_credits")
    elif not has_string_list_items(credits.get("composer")):
        checks.append("missing_composer")
    elif has_suspicious_credit_values(credits.get("composer")):
        checks.append("suspicious_composer")

    introduction = detail.get("introduction")
    if not has_string_list_items(introduction):
        checks.append("missing_introduction")

    videos = detail.get("videos")
    if count_videos(videos) == 0:
        checks.append("missing_primary_videos")

    detail_year = detail.get("published_year")
    if not isinstance(detail_year, int) and stored_year is None:
        checks.append("missing_published_year")
    elif isinstance(detail_year, int) and is_suspicious_year(detail_year):
        checks.append("suspicious_published_year")
    elif isinstance(stored_year, int) and is_suspicious_year(stored_year):
        checks.append("suspicious_published_year")
    if isinstance(detail_year, int) and isinstance(stored_year, int) and detail_year != stored_year:
        checks.append("published_year_mismatch")

    return checks


def has_string_list_items(value: object) -> bool:
    return isinstance(value, list) and any(isinstance(item, str) and item.strip() for item in value)


def has_suspicious_credit_values(value: object) -> bool:
    if not isinstance(value, list):
        return False
    for item in value:
        if not isinstance(item, str):
            continue
        normalized = item.casefold()
        if any(token in normalized for token in SUSPICIOUS_CREDIT_TOKENS):
            return True
    return False


def is_suspicious_year(value: int) -> bool:
    return value < 2000 or value > datetime.now().year + 1


def count_videos(value: object) -> int:
    if not isinstance(value, dict):
        return 0
    count = 0
    for entries in value.values():
        if isinstance(entries, list):
            count += sum(1 for entry in entries if isinstance(entry, dict) and entry.get("id"))
    return count
