import unittest
from unittest.mock import patch
from tests.helpers import temporary_db, raw_song, MELT_URL
from vocaloid_title_search.database import save_song_detail_entry, load_metadata, load_song_detail
from vocaloid_title_search.database_quality import validate_database_quality
from vocaloid_title_search.video_metadata import refresh_stored_video_metadata, is_fallback_metadata

from vocaloid_title_search.detail import fallback_niconico_thumbnail_url
from vocaloid_title_search.video_metadata import (
    apply_video_metadata,
    collect_video_ids,
    summarize_video_metadata,
)


class VideoMetadataTests(unittest.TestCase):
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
