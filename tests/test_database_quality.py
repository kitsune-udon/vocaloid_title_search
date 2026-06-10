import json
import sqlite3
from contextlib import closing, redirect_stdout
from io import StringIO
import unittest

from tests.helpers import MELT_URL, raw_song, temporary_db
from vocaloid_title_search.cli.validate_db import main as validate_db_main
from vocaloid_title_search.database import rebuild_database, save_song_detail_entry
from vocaloid_title_search.database_quality import validate_database_quality


class DatabaseQualityTests(unittest.TestCase):
    def test_complete_database_passes_quality_check(self) -> None:
        with temporary_db([raw_song()]) as db_path:
            save_song_detail_entry(
                db_path,
                MELT_URL,
                {
                    "page_title": "メルト",
                    "source_url": MELT_URL,
                    "published_year": 2007,
                    "credits": {"composer": ["ryo"]},
                    "videos": [
                        {
                            "service": "niconico",
                            "id": "sm1715919",
                            "title": "メルト",
                            "thumbnail_url": "https://example.test/thumb.jpg",
                        }
                    ],
                },
            )

            report = validate_database_quality(db_path)

            self.assertTrue(report.ok)
            self.assertEqual(report.counts["songs"], 1)
            self.assertEqual(report.counts["details"], 1)
            self.assertEqual(report.counts["songs_with_composer"], 1)
            self.assertEqual(report.counts["songs_with_published_year"], 1)
            self.assertEqual(report.counts["videos"], 1)
            self.assertEqual(report.counts["videos_with_thumbnail"], 1)

    def test_database_with_missing_detail_fails_quality_check(self) -> None:
        with temporary_db() as db_path:
            rebuild_database(db_path, [raw_song()], {}, "source")

            report = validate_database_quality(db_path)

            self.assertFalse(report.ok)
            self.assertIn(
                "song_details count must match songs count: details=0, songs=1",
                report.errors,
            )

    def test_invalid_detail_json_fails_quality_check(self) -> None:
        with temporary_db([raw_song()]) as db_path:
            save_song_detail_entry(db_path, MELT_URL, {"page_title": "メルト", "source_url": MELT_URL})
            with closing(sqlite3.connect(db_path)) as connection:
                connection.execute(
                    "UPDATE song_details SET payload_json = ? WHERE url = ?",
                    ("{", MELT_URL),
                )
                connection.commit()

            report = validate_database_quality(db_path)

            self.assertFalse(report.ok)
            self.assertIn("song_details has invalid JSON rows: 1", report.errors)

    def test_validate_db_cli_json_returns_nonzero_for_missing_database(self) -> None:
        with temporary_db() as db_path:
            missing_path = db_path.with_name("missing.sqlite3")

            with redirect_stdout(StringIO()):
                status = validate_db_main(["--db-path", str(missing_path), "--json"])

            self.assertEqual(status, 1)

    def test_report_can_be_serialized_to_json(self) -> None:
        with temporary_db([raw_song()]) as db_path:
            report = validate_database_quality(db_path)

            serialized = json.dumps(report.to_dict(), ensure_ascii=False)

            self.assertIn('"ok": true', serialized)


if __name__ == "__main__":
    unittest.main()
