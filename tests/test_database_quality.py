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

    def test_corrupt_song_search_values_are_rejected_without_count_changes(self):
        from tools.export_d1_sql import export_atomic
        changes = ["title_length=999", "title='wrong'", "artist='wrong'",
                   "artist_note='wrong'", "sort_order=0", "popularity_score=-1",
                   "popularity_label='unknown'"]
        for change in changes:
            with self.subTest(change=change), temporary_db([raw_song()]) as path:
                with closing(sqlite3.connect(path)) as connection:
                    connection.execute("UPDATE songs SET " + change)
                    connection.commit()
                    report = validate_database_quality(path)
                    self.assertFalse(report.ok)
                    self.assertEqual(report.counts["invalid_song_values"], 1)
                    with self.assertRaisesRegex(ValueError, "invalid song values"):
                        export_atomic(connection, path.with_suffix(".sql"), publish=True)

    def test_duplicate_sort_positions_are_rejected(self):
        with temporary_db([raw_song(), raw_song("別曲", "https://w.atwiki.jp/hmiku/pages/2.html")]) as path:
            with closing(sqlite3.connect(path)) as connection:
                connection.execute("UPDATE songs SET sort_order=1")
                connection.commit()
            self.assertFalse(validate_database_quality(path).ok)

    def test_service_grouped_videos_are_counted(self) -> None:
        with temporary_db([raw_song()]) as db_path:
            save_song_detail_entry(db_path, MELT_URL, {
                "videos": {
                    "niconico": [{"id": "sm1715919", "title": "メルト"}],
                    "youtube": [{"id": "example", "thumbnail_url": "https://example.test/thumb.jpg"}],
                },
                "related_videos": {"niconico": [{"id": "sm2183246"}], "youtube": []},
            })
            report = validate_database_quality(db_path)
            self.assertEqual(report.counts["videos"], 2)
            self.assertEqual(report.counts["related_videos"], 1)
            self.assertEqual(report.counts["videos_with_title"], 1)
            self.assertEqual(report.counts["videos_with_thumbnail"], 1)

    def test_valid_json_that_is_not_an_object_fails_cleanly(self) -> None:
        for payload in ("null", "[]", "42", '\"text\"'):
            with self.subTest(payload=payload), temporary_db([raw_song()]) as db_path:
                with closing(sqlite3.connect(db_path)) as connection:
                    connection.execute("UPDATE song_details SET payload_json = ?", (payload,))
                    connection.commit()
                report = validate_database_quality(db_path)
                self.assertFalse(report.ok)
                self.assertEqual(report.counts["invalid_detail_json"], 1)

    def test_publication_requires_metadata_refresh_for_present_services(self) -> None:
        with temporary_db([raw_song()]) as db_path:
            save_song_detail_entry(db_path, MELT_URL, {"videos": {"youtube": [{"id": "video"}]}})
            self.assertTrue(validate_database_quality(db_path).ok)
            report = validate_database_quality(db_path, require_video_metadata=True)
            self.assertFalse(report.ok)
            self.assertTrue(any("youtube metadata refresh" in error for error in report.errors))

    def test_publication_rejects_bad_detail_shapes_and_unsafe_links(self):
        from tests.helpers import complete_detail
        from tools.export_d1_sql import export_atomic
        broken = [
            {"credits": {"composer": "ryo"}}, {"introduction": "text"},
            {"published_year": True}, {"page_title": 123},
            {"source_url": "https://example.test/wrong-source"},
            {"videos": {"youtube": ["bad entry"]}},
            {"videos": {"youtube": [{"id": "video", "url": "javascript:alert(1)", "title": "title", "thumbnail_url": ""}]}},
        ]
        for fields in broken:
            with self.subTest(fields=fields), temporary_db([raw_song()]) as path:
                payload = complete_detail({})
                payload.update(fields)
                with closing(sqlite3.connect(path)) as connection:
                    connection.execute("UPDATE song_details SET payload_json=?", (json.dumps(payload),))
                    connection.commit()
                    self.assertFalse(validate_database_quality(path, require_video_metadata=True).ok)
                    with self.assertRaisesRegex(ValueError, "invalid detail contract"):
                        export_atomic(connection, path.with_suffix(".sql"), publish=True)

    def test_search_index_must_match_detail_values_not_only_row_counts(self):
        from tests.helpers import complete_detail
        with temporary_db([raw_song()]) as path:
            save_song_detail_entry(path, MELT_URL, complete_detail({"credits": {"composer": ["Correct"]}, "published_year": 2020}))
            with closing(sqlite3.connect(path)) as connection:
                connection.execute("UPDATE song_credit_people SET name='Wrong', normalized_name='wrong'")
                connection.execute("UPDATE song_details SET published_year=1999")
                connection.commit()
            report = validate_database_quality(path)
            self.assertFalse(report.ok)
            self.assertEqual(report.counts["detail_index_mismatch"], 1)

    def test_publication_requires_complete_detail_but_local_reports_allow_partial(self):
        with temporary_db([raw_song()]) as path:
            save_song_detail_entry(path, MELT_URL, {"page_title": "partial"})
            self.assertTrue(validate_database_quality(path).ok)
            report = validate_database_quality(path, require_video_metadata=True)
            self.assertFalse(report.ok)
            self.assertEqual(report.counts["invalid_detail_contract"], 1)

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
