import json
import unittest
from contextlib import closing
import sqlite3

from tests.helpers import raw_song, temporary_db
from vocaloid_title_search.database import save_song_detail_entry
from vocaloid_title_search.database_quality import validate_database_quality
from vocaloid_title_search.quality_policy import QualityPolicy, compare_counts, video_refresh_errors


class PublicationPolicyTests(unittest.TestCase):
    def test_count_and_coverage_drops_are_independent(self):
        old = {"songs": 100, "songs_with_composer": 100}
        _, errors = compare_counts({"songs": 130, "songs_with_composer": 100}, old, QualityPolicy())
        self.assertTrue(any("coverage" in e for e in errors))
        _, errors = compare_counts({"songs": 79, "songs_with_composer": 79}, old, QualityPolicy())
        self.assertTrue(any("songs decreased" in e for e in errors))
        _, errors = compare_counts({"songs": 100, "songs_with_composer": 100}, old, QualityPolicy())
        self.assertEqual(errors, [])

    def test_actual_database_comparison_and_missing_baseline(self):
        songs = [raw_song(str(n), f"https://w.atwiki.jp/hmiku/pages/{n}.html") for n in range(10)]
        with temporary_db(songs) as old, temporary_db(songs[:1]) as new:
            report = validate_database_quality(new, baseline_path=old)
            self.assertFalse(report.ok)
            self.assertEqual(report.comparison["songs"], {"before": 10, "after": 1})
            self.assertFalse(validate_database_quality(new, baseline_path=old.with_name("missing")).ok)

    def test_video_rates_and_inconsistent_counts(self):
        prefix = "video_metadata_youtube_"
        metadata = {prefix + key: str(value) for key, value in {"total": 100, "success": 79, "failure": 1, "fallback": 20, "retained": 20}.items()}
        self.assertTrue(video_refresh_errors(metadata, "youtube", 100, QualityPolicy()))
        metadata[prefix + "success"] = "80"
        metadata[prefix + "failure"] = "0"
        self.assertEqual(video_refresh_errors(metadata, "youtube", 100, QualityPolicy()), [])
        previous = {prefix + "total": "100", prefix + "success": "100"}
        self.assertTrue(video_refresh_errors(metadata, "youtube", 100, QualityPolicy(), previous))
        metadata[prefix + "failure"] = "-1"
        self.assertIn("inconsistent", video_refresh_errors(metadata, "youtube", 100, QualityPolicy())[0])

    def test_policy_rejects_nonfinite_or_out_of_range_thresholds(self):
        for value in (-1, 2, float("nan"), float("inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                QualityPolicy(min_video_success_rate=value)
