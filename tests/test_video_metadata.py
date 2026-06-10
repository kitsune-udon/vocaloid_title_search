import unittest

from vocaloid_title_search.detail import fallback_niconico_thumbnail_url
from vocaloid_title_search.video_metadata import (
    apply_video_metadata,
    collect_video_ids,
    summarize_video_metadata,
)


class VideoMetadataTests(unittest.TestCase):
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
