import json
import sqlite3
from contextlib import closing
import unittest
from unittest.mock import patch
from tests.helpers import temporary_db, raw_song, MELT_URL
from vocaloid_title_search.database import load_metadata, load_song_detail
from tests.helpers import save_complete_detail as save_song_detail_entry
from vocaloid_title_search.database_quality import validate_database_quality
from vocaloid_title_search.video_metadata import refresh_stored_video_metadata, is_fallback_metadata

from vocaloid_title_search.detail import fallback_niconico_thumbnail_url
from vocaloid_title_search.video_metadata import (
    apply_video_metadata,
    collect_video_ids,
    summarize_video_metadata,
)


class VideoMetadataTests(unittest.TestCase):
    def test_refresh_respects_build_lock_before_network_access(self):
        from vocaloid_title_search.build_checkpoint import build_lock
        with temporary_db([raw_song()]) as path, build_lock(path):
            before = path.read_bytes()
            with patch("vocaloid_title_search.video_metadata.fetch_all_video_metadata") as fetcher:
                self.assertEqual(refresh_stored_video_metadata(path, max_workers=1, timeout=1), 1)
                fetcher.assert_not_called()
            self.assertEqual(before, path.read_bytes())

    def test_identical_refresh_does_not_rewrite_detail_rows(self):
        with temporary_db([raw_song()]) as path:
            save_song_detail_entry(path, MELT_URL, {"videos": {"niconico": [{"id": "sm1"}]}})
            fresh = {"niconico": {"sm1": {"title": "Real title", "thumbnail_url": "https://example.test/image.jpg"}}, "youtube": {}}
            with patch("vocaloid_title_search.video_metadata.fetch_all_video_metadata", return_value=fresh):
                self.assertEqual(refresh_stored_video_metadata(path, max_workers=1, timeout=1), 0)
                with closing(sqlite3.connect(path)) as connection:
                    connection.executescript("""
                        CREATE TRIGGER reject_detail_rewrite BEFORE UPDATE ON song_details
                        BEGIN SELECT RAISE(ABORT, 'unchanged row was rewritten'); END;
                    """)
                self.assertEqual(refresh_stored_video_metadata(path, max_workers=1, timeout=1), 0)
            self.assertTrue(validate_database_quality(path, require_video_metadata=True).ok)

    def test_repeated_metadata_fetch_is_fresh_within_one_process(self):
        from vocaloid_title_search.video_metadata import youtube_video_metadata
        with patch("vocaloid_title_search.video_metadata.fetch_text", side_effect=[
            '{"title":"first","thumbnail_url":"https://example.test/first.jpg"}',
            '{"title":"second","thumbnail_url":"https://example.test/second.jpg"}',
        ]) as fetcher:
            self.assertEqual(youtube_video_metadata("video")["title"], "first")
            self.assertEqual(youtube_video_metadata("video")["title"], "second")
            self.assertEqual(fetcher.call_count, 2)

    def test_diagnostics_distinguish_deleted_http_and_invalid_responses(self):
        import urllib.error
        from vocaloid_title_search.video_metadata import niconico_video_metadata, youtube_video_metadata
        with patch("vocaloid_title_search.video_metadata.fetch_text", return_value='<nicovideo_thumb_response status="fail"><error><code>DELETED</code></error></nicovideo_thumb_response>'):
            self.assertEqual(niconico_video_metadata("sm1")["fetch_error"], "provider_DELETED")
        for fetcher in (niconico_video_metadata, youtube_video_metadata):
            with patch("vocaloid_title_search.video_metadata.fetch_text", side_effect=urllib.error.HTTPError("https://example.test", 429, "limited", {}, None)):
                self.assertEqual(fetcher("sm1")["fetch_error"], "http_429")
            with patch("vocaloid_title_search.video_metadata.fetch_text", return_value='broken response'):
                self.assertEqual(fetcher("sm1")["fetch_error"], "invalid_response")

    def test_service_diagnostics_record_failed_ids_without_response_bodies(self):
        import time
        from vocaloid_title_search.video_metadata import fetch_service_video_metadata
        messages = []
        fetch_service_video_metadata("niconico", ["sm1", "sm2"],
            lambda identifier: {"title": "ニコニコ動画", "thumbnail_url": "fallback", "fetch_error": "http_429"},
            max_workers=1, started_at=time.perf_counter(), progress=messages.append)
        report = next(message for message in messages if "取得診断" in message)
        self.assertEqual(json.loads(report.split(": ", 1)[1]), {"http_429": ["sm1", "sm2"]})

    def test_diagnostic_fields_do_not_enter_public_video_payload(self):
        video = {"id": "sm1"}
        detail = {"videos": {"niconico": [video]}}
        apply_video_metadata(detail, {"niconico": {"sm1": {
            "title": "ニコニコ動画", "thumbnail_url": "https://example.test/image.jpg", "fetch_error": "http_429",
        }}, "youtube": {}})
        self.assertNotIn("fetch_error", video)

    def test_official_url_matching_fallback_is_still_success(self) -> None:
        self.assertFalse(is_fallback_metadata("niconico", "sm1", {
            "title": "Real title", "thumbnail_url": fallback_niconico_thumbnail_url("sm1"),
        }))

    def test_fallback_does_not_replace_existing_good_metadata(self) -> None:
        video = {"id": "sm1", "title": "Saved title", "thumbnail_url": "https://example.test/saved.jpg"}
        detail = {"videos": {"niconico": [video]}}
        updated = apply_video_metadata(detail, {"niconico": {"sm1": {
            "title": "ニコニコ動画", "thumbnail_url": fallback_niconico_thumbnail_url("sm1"),
        }}, "youtube": {}})
        self.assertEqual(updated, 0)
        self.assertEqual(video["title"], "Saved title")
        self.assertEqual(video["thumbnail_url"], "https://example.test/saved.jpg")

    def test_service_outage_leaves_database_unchanged(self) -> None:
        with temporary_db([raw_song()]) as db_path:
            save_song_detail_entry(db_path, MELT_URL, {"videos": {"niconico": [{"id": "sm1"}]}})
            before = db_path.read_bytes()
            with patch("vocaloid_title_search.video_metadata.fetch_all_video_metadata", return_value={
                "niconico": {"sm1": {"title": "ニコニコ動画", "thumbnail_url": "fallback"}}, "youtube": {},
            }):
                self.assertEqual(refresh_stored_video_metadata(db_path, max_workers=1, timeout=1), 1)
            self.assertEqual(db_path.read_bytes(), before)

    def test_refresh_records_both_service_results(self) -> None:
        with temporary_db([raw_song()]) as db_path:
            save_song_detail_entry(db_path, MELT_URL, {"videos": {"niconico": [{"id": "sm1"}]}})
            with patch("vocaloid_title_search.video_metadata.fetch_all_video_metadata", return_value={
                "niconico": {"sm1": {"title": "Real title", "thumbnail_url": "https://example.test/image.jpg"}}, "youtube": {},
            }):
                self.assertEqual(refresh_stored_video_metadata(db_path, max_workers=1, timeout=1), 0)
            metadata = load_metadata(db_path)
            self.assertEqual(metadata["video_metadata_niconico_total"], "1")
            self.assertEqual(metadata["video_metadata_niconico_success"], "1")
            self.assertEqual(metadata["video_metadata_youtube_total"], "0")
            self.assertTrue(validate_database_quality(db_path, require_video_metadata=True).ok)
            save_song_detail_entry(db_path, MELT_URL, {"videos": {"niconico": [{"id": "sm2"}]}})
            self.assertFalse(validate_database_quality(db_path, require_video_metadata=True).ok)

    def test_rebuild_keeps_saved_metadata_when_one_video_falls_back(self) -> None:
        with temporary_db([raw_song()]) as old, temporary_db([raw_song()]) as candidate:
            save_song_detail_entry(old, MELT_URL, {"videos": {"niconico": [{
                "id": "sm1", "title": "Saved title", "thumbnail_url": "https://example.test/saved.jpg",
            }]}})
            save_song_detail_entry(candidate, MELT_URL, {"videos": {"niconico": [{"id": "sm1"}, {"id": "sm2"}]}})
            with patch("vocaloid_title_search.video_metadata.fetch_all_video_metadata", return_value={
                "niconico": {
                    "sm1": {"title": "ニコニコ動画", "thumbnail_url": "fallback"},
                    "sm2": {"title": "New title", "thumbnail_url": "https://example.test/new.jpg"},
                }, "youtube": {},
            }):
                self.assertEqual(refresh_stored_video_metadata(candidate, max_workers=1, timeout=1, previous_db_path=old), 0)
            videos = load_song_detail(candidate, MELT_URL)["videos"]["niconico"]
            self.assertEqual([video["title"] for video in videos], ["Saved title", "New title"])
            report = validate_database_quality(candidate, require_video_metadata=True)
            self.assertFalse(report.ok)  # Preserved old data does not count as a fresh success.
            self.assertEqual(report.metadata["video_metadata_niconico_retained"], "1")

    def test_collect_video_ids_deduplicates_ids(self) -> None:
        detail = {
            "videos": {
                "niconico": [{"id": "sm1"}, {"id": "sm1"}],
                "youtube": [{"id": "abc12345678"}],
            },
            "related_videos": {
                "niconico": [{"id": "sm2"}],
                "youtube": [{"id": "abc12345678"}],
            },
        }

        ids = collect_video_ids([("url", detail)])

        self.assertEqual(ids["niconico"], ["sm1", "sm2"])
        self.assertEqual(ids["youtube"], ["abc12345678"])

    def test_apply_video_metadata_updates_all_video_sections(self) -> None:
        detail = {
            "videos": {
                "niconico": [{"id": "sm123", "title": "old", "thumbnail_url": "old"}],
                "youtube": [{"id": "abc12345678", "title": "old", "thumbnail_url": "old"}],
            },
            "related_videos": {
                "niconico": [{"id": "sm123", "title": "old", "thumbnail_url": "old"}],
                "youtube": [],
            },
        }

        updated = apply_video_metadata(
            detail,
            {
                "niconico": {
                    "sm123": {
                        "title": "nico title",
                        "thumbnail_url": "https://example.test/nico.jpg",
                    }
                },
                "youtube": {
                    "abc12345678": {
                        "title": "yt title",
                        "thumbnail_url": "https://example.test/yt.jpg",
                    }
                },
            },
        )

        self.assertEqual(updated, 3)
        self.assertEqual(detail["videos"]["niconico"][0]["title"], "nico title")
        self.assertIn(
            "https://example.test/nico.jpg",
            detail["related_videos"]["niconico"][0]["thumbnail_urls"],
        )
        self.assertEqual(detail["videos"]["youtube"][0]["title"], "yt title")
        self.assertEqual(
            detail["videos"]["youtube"][0]["thumbnail_urls"],
            [
                "https://example.test/yt.jpg",
                "https://img.youtube.com/vi/abc12345678/maxresdefault.jpg",
                "https://img.youtube.com/vi/abc12345678/hqdefault.jpg",
                "https://img.youtube.com/vi/abc12345678/mqdefault.jpg",
                "https://img.youtube.com/vi/abc12345678/default.jpg",
            ],
        )

    def test_summarize_video_metadata_counts_success_failure_and_fallback(self) -> None:
        summary = summarize_video_metadata(
            {
                "niconico": ["sm1", "sm2"],
                "youtube": ["abc12345678", "missing12345"],
            },
            {
                "niconico": {
                    "sm1": {
                        "title": "nico title",
                        "thumbnail_url": "https://example.test/nico.jpg",
                    },
                    "sm2": {
                        "title": "ニコニコ動画",
                        "thumbnail_url": fallback_niconico_thumbnail_url("sm2"),
                    },
                },
                "youtube": {
                    "abc12345678": {
                        "title": "yt title",
                        "thumbnail_url": "https://example.test/yt.jpg",
                    },
                },
            },
        )

        self.assertEqual(summary, {"total": 4, "success": 2, "failure": 1, "fallback": 1})


if __name__ == "__main__":
    unittest.main()
