import sqlite3
import unittest
from contextlib import redirect_stdout
from io import StringIO

from tests.helpers import MELT_URL, raw_song, temporary_db
from vocaloid_title_search.cli.report_detail_quality import main as report_detail_quality_main
from vocaloid_title_search.database import save_song_detail_entry
from vocaloid_title_search.detail_quality import report_detail_quality


class DetailQualityTests(unittest.TestCase):
    def test_report_counts_missing_detail_fields(self) -> None:
        with temporary_db([raw_song()]) as db_path:
            save_song_detail_entry(
                db_path,
                MELT_URL,
                {
                    "page_title": "メルト",
                    "source_url": MELT_URL,
                    "credits": {},
                    "introduction": [],
                    "videos": {"niconico": [], "youtube": []},
                },
            )

            report = report_detail_quality(db_path)

            self.assertEqual(report.total_details, 1)
            self.assertEqual(report.total_issues, 1)
            self.assertEqual(
                report.issues[0].checks,
                [
                    "missing_credits",
                    "missing_introduction",
                    "missing_primary_videos",
                    "missing_published_year",
                ],
            )
            self.assertEqual(report.issue_counts["missing_credits"], 1)

    def test_limit_zero_keeps_counts_without_issue_rows(self) -> None:
        with temporary_db([raw_song()]) as db_path:
            save_song_detail_entry(
                db_path,
                MELT_URL,
                {
                    "page_title": "メルト",
                    "source_url": MELT_URL,
                    "credits": {},
                    "introduction": [],
                    "videos": {"niconico": [], "youtube": []},
                },
            )

            report = report_detail_quality(db_path, limit=0)

            self.assertEqual(report.total_issues, 1)
            self.assertEqual(report.issues, [])

    def test_complete_detail_has_no_issues(self) -> None:
        with temporary_db([raw_song()]) as db_path:
            save_song_detail_entry(
                db_path,
                MELT_URL,
                {
                    "page_title": "メルト",
                    "source_url": MELT_URL,
                    "published_year": 2007,
                    "credits": {"composer": ["ryo"]},
                    "introduction": ["紹介文"],
                    "videos": {"niconico": [{"id": "sm1715919"}], "youtube": []},
                },
            )

            report = report_detail_quality(db_path)

            self.assertEqual(report.total_issues, 0)
            self.assertTrue(all(count == 0 for count in report.issue_counts.values()))

    def test_report_flags_suspicious_composer_and_published_year(self) -> None:
        with temporary_db([raw_song()]) as db_path:
            save_song_detail_entry(
                db_path,
                MELT_URL,
                {
                    "page_title": "メルト",
                    "source_url": MELT_URL,
                    "published_year": 1999,
                    "credits": {"composer": ["ryo（Twitter）"]},
                    "introduction": ["紹介文"],
                    "videos": {"niconico": [{"id": "sm1715919"}], "youtube": []},
                },
            )

            report = report_detail_quality(db_path)

            self.assertIn("suspicious_composer", report.issues[0].checks)
            self.assertIn("suspicious_published_year", report.issues[0].checks)

    def test_report_flags_published_year_mismatch(self) -> None:
        with temporary_db([raw_song()]) as db_path:
            save_song_detail_entry(
                db_path,
                MELT_URL,
                {
                    "page_title": "メルト",
                    "source_url": MELT_URL,
                    "published_year": 2007,
                    "credits": {"composer": ["ryo"]},
                    "introduction": ["紹介文"],
                    "videos": {"niconico": [{"id": "sm1715919"}], "youtube": []},
                },
            )
            with sqlite3.connect(db_path) as connection:
                connection.execute(
                    "UPDATE song_details SET published_year = ? WHERE url = ?",
                    (2008, MELT_URL),
                )

            report = report_detail_quality(db_path)

            self.assertEqual(report.issues[0].checks, ["published_year_mismatch"])
            self.assertEqual(report.issue_counts["published_year_mismatch"], 1)

    def test_report_detail_quality_cli_returns_zero(self) -> None:
        with temporary_db([raw_song()]) as db_path:
            with redirect_stdout(StringIO()):
                status = report_detail_quality_main(["--db-path", str(db_path), "--limit", "0"])

            self.assertEqual(status, 0)


if __name__ == "__main__":
    unittest.main()
