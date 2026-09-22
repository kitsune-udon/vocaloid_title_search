import io
import unittest
from contextlib import closing, redirect_stderr
from unittest.mock import patch
from tests.helpers import temporary_db, raw_song
from vocaloid_title_search.database import save_song_detail_entry
from vocaloid_title_search.cli.build_db import build_database

from vocaloid_title_search.cli.common import (
    DEFAULT_BACKOFF_BASE,
    DEFAULT_BACKOFF_MAX,
    DEFAULT_MAX_RETRIES,
    DEFAULT_REQUEST_INTERVAL,
    DEFAULT_TIMEOUT,
)
from vocaloid_title_search.cli.build_db import DEFAULT_BUILD_WORKERS
from vocaloid_title_search.cli.build_db import parse_args


class BuildDbCliTests(unittest.TestCase):
    def test_failed_metadata_refresh_preserves_existing_database(self) -> None:
        with temporary_db([raw_song()]) as db_path:
            before = db_path.read_bytes()
            args = parse_args(["--db-path", str(db_path), "--with-video-metadata"])
            with patch("vocaloid_title_search.cli.build_db.build_title_corpus", return_value=([raw_song()], {})), \
                 patch("vocaloid_title_search.cli.build_db.build_song_details", return_value=0), \
                 patch("vocaloid_title_search.cli.build_db.refresh_stored_video_metadata", return_value=1):
                self.assertEqual(build_database(args), 1)
            self.assertEqual(db_path.read_bytes(), before)
            self.assertEqual(list(db_path.parent.glob(".*.build.*sqlite3")), [])

    def test_quality_failure_preserves_existing_database(self) -> None:
        with temporary_db([raw_song()]) as db_path:
            before = db_path.read_bytes()
            with patch("vocaloid_title_search.cli.build_db.build_title_corpus", return_value=([raw_song()], {})), \
                 patch("vocaloid_title_search.cli.build_db.build_song_details", return_value=0):
                self.assertEqual(build_database(parse_args(["--db-path", str(db_path)])), 1)
            self.assertEqual(db_path.read_bytes(), before)

    def test_complete_candidate_replaces_database(self) -> None:
        with temporary_db([raw_song()]) as db_path:
            def add_details(args, candidate):
                song = raw_song("新曲")
                save_song_detail_entry(candidate, song.url, {"page_title": song.raw_title})
                return 0
            with patch("vocaloid_title_search.cli.build_db.build_title_corpus", return_value=([raw_song("新曲")], {})), \
                 patch("vocaloid_title_search.cli.build_db.build_song_details", side_effect=add_details):
                self.assertEqual(build_database(parse_args(["--db-path", str(db_path)])), 0)
            import sqlite3
            with closing(sqlite3.connect(db_path)) as connection:
                self.assertEqual(connection.execute("SELECT title FROM songs").fetchone()[0], "新曲")

    def test_default_options_are_practical_for_full_build(self) -> None:
        args = parse_args([])

        self.assertEqual(args.workers, DEFAULT_BUILD_WORKERS)
        self.assertEqual(args.timeout, DEFAULT_TIMEOUT)
        self.assertEqual(args.request_interval, DEFAULT_REQUEST_INTERVAL)
        self.assertEqual(args.max_retries, DEFAULT_MAX_RETRIES)
        self.assertEqual(args.backoff_base, DEFAULT_BACKOFF_BASE)
        self.assertEqual(args.backoff_max, DEFAULT_BACKOFF_MAX)

    def test_workers_sets_detail_fetch_workers(self) -> None:
        args = parse_args(["--workers", "3"])

        self.assertEqual(args.workers, 3)

    def test_rejects_negative_request_interval(self) -> None:
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as context:
            parse_args(["--request-interval", "-1"])
        self.assertEqual(context.exception.code, 2)

    def test_rejects_zero_timeout(self) -> None:
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as context:
            parse_args(["--timeout", "0"])
        self.assertEqual(context.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
