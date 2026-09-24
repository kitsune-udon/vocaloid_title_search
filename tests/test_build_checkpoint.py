from contextlib import closing
from datetime import datetime, timedelta, timezone
import sqlite3
import unittest
from unittest.mock import patch

from tests.helpers import raw_song, temporary_db, complete_detail
from vocaloid_title_search.build_checkpoint import build_lock, mark_checkpoint, reuse_details
from vocaloid_title_search.cli.build_db import build_database, parse_args
from vocaloid_title_search.database import save_song_detail_entry

MODULE = "vocaloid_title_search.cli.build_db."


class BuildCheckpointTests(unittest.TestCase):
    def test_failed_build_resumes_only_missing_details(self):
        first, second = raw_song(), raw_song("別曲", "https://w.atwiki.jp/hmiku/pages/2.html")
        with temporary_db([first]) as target:
            before = target.read_bytes()
            args = parse_args(["--db-path", str(target), "--resume"])
            def fetch(url, **kwargs):
                if url == second.url:
                    raise TimeoutError("retry later")
                return {"page_title": "メルト"}
            with patch(MODULE + "build_title_corpus", return_value=([first, second], {})), patch(MODULE + "fetch_song_detail", side_effect=fetch):
                self.assertEqual(build_database(args), 1)
            self.assertEqual(target.read_bytes(), before)
            checkpoint = target.with_name(f".{target.name}.build.checkpoint.sqlite3")
            self.assertTrue(checkpoint.exists())
            with patch(MODULE + "build_title_corpus") as corpus, patch(MODULE + "fetch_song_detail", return_value={"page_title": "別曲"}) as fetcher:
                self.assertEqual(build_database(args), 0)
                corpus.assert_not_called()
                fetcher.assert_called_once_with(second.url, timeout=args.timeout)
            self.assertFalse(checkpoint.exists())
            with closing(sqlite3.connect(target)) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM song_details").fetchone()[0], 2)

    def test_failed_final_replace_preserves_checkpoint_for_retry(self):
        import os
        with temporary_db([raw_song()]) as target:
            checkpoint = target.with_name(f".{target.name}.build.checkpoint.sqlite3")
            args = parse_args(["--db-path", str(target), "--resume"])
            checkpoint.write_bytes(target.read_bytes())
            mark_checkpoint(checkpoint, args)
            before = target.read_bytes()
            original_replace = os.replace
            def fail_publish(source, destination):
                if destination == target:
                    raise OSError("simulated final rename failure")
                return original_replace(source, destination)
            with patch(MODULE + "os.replace", side_effect=fail_publish):
                self.assertEqual(build_database(args), 1)
            self.assertEqual(target.read_bytes(), before)
            self.assertTrue(checkpoint.exists())
            with patch(MODULE + "fetch_song_detail") as fetcher, patch(MODULE + "build_title_corpus") as corpus:
                self.assertEqual(build_database(args), 0)
                fetcher.assert_not_called()
                corpus.assert_not_called()
            self.assertFalse(checkpoint.exists())
            with closing(sqlite3.connect(target)) as connection:
                self.assertIsNone(connection.execute("SELECT value FROM metadata WHERE key='build_checkpoint'").fetchone())

    def test_incompatible_checkpoint_is_preserved_and_rejected(self):
        with temporary_db([raw_song()]) as target:
            checkpoint = target.with_name(f".{target.name}.build.checkpoint.sqlite3")
            checkpoint.write_bytes(target.read_bytes())
            args = parse_args(["--db-path", str(target), "--resume"])
            mark_checkpoint(checkpoint, args)
            before = checkpoint.read_bytes()
            args.source_url = "https://example.test/changed"
            self.assertEqual(build_database(args), 1)
            self.assertEqual(checkpoint.read_bytes(), before)

    def test_changed_corpus_parser_rejects_resume_before_fetching(self):
        with temporary_db([raw_song()]) as target:
            checkpoint = target.with_name(f".{target.name}.build.checkpoint.sqlite3")
            checkpoint.write_bytes(target.read_bytes())
            args = parse_args(["--db-path", str(target), "--resume"])
            mark_checkpoint(checkpoint, args)
            before = checkpoint.read_bytes()
            with patch("vocaloid_title_search.build_checkpoint.corpus_fingerprint", return_value="changed"), patch(MODULE + "fetch_song_detail") as fetcher:
                self.assertEqual(build_database(args), 1)
                fetcher.assert_not_called()
            self.assertEqual(checkpoint.read_bytes(), before)

    def test_detail_reuse_uses_source_time_not_metadata_refresh_time(self):
        with temporary_db([raw_song()]) as old, temporary_db([raw_song()]) as candidate:
            args = parse_args(["--db-path", str(old)])
            mark_checkpoint(old, args)
            save_song_detail_entry(old, raw_song().url, complete_detail({"credits": {"composer": ["kept"]}}))
            self.assertEqual(reuse_details(old, candidate, 7), 1)
            with closing(sqlite3.connect(old)) as connection:
                connection.execute("UPDATE song_details SET source_fetched_at=?", ((datetime.now(timezone.utc) - timedelta(days=8)).isoformat(),))
                connection.commit()
            self.assertEqual(reuse_details(old, candidate, 7), 0)

    def test_resume_refetches_malformed_stored_detail(self):
        import json
        from vocaloid_title_search.cli.build_db import build_song_details
        with temporary_db([raw_song()]) as target:
            with closing(sqlite3.connect(target)) as connection:
                connection.execute("UPDATE song_details SET payload_json=?", (json.dumps({"introduction": "invalid"}),))
                connection.commit()
            with patch(MODULE + "fetch_song_detail", return_value=complete_detail({})) as fetcher:
                self.assertEqual(build_song_details(parse_args(["--db-path", str(target)]), target), 0)
                fetcher.assert_called_once()

    def test_empty_tag_response_preserves_existing_database(self):
        with temporary_db([raw_song()]) as target:
            before = target.read_bytes()
            with patch("vocaloid_title_search.wiki.WikiClient.fetch_html", side_effect=[
                '<div class="cmd_tag"><ul class="atwiki-page-list"><li><a href="/hmiku/pages/82.html">メルト</a></li></ul></div>',
                '<html>maintenance</html>',
            ]):
                self.assertEqual(build_database(parse_args(["--db-path", str(target)])), 1)
            self.assertEqual(target.read_bytes(), before)

    def test_tag_failure_preserves_existing_database(self):
        import urllib.error
        from vocaloid_title_search.wiki import DEFAULT_TAG_URL
        with temporary_db([raw_song()]) as target:
            before = target.read_bytes()
            def fetch(url, pages):
                if url == DEFAULT_TAG_URL:
                    return [raw_song()]
                raise urllib.error.URLError("tag unavailable")
            with patch("vocaloid_title_search.wiki.WikiClient.fetch_songs", side_effect=fetch):
                self.assertEqual(build_database(parse_args(["--db-path", str(target)])), 1)
            self.assertEqual(target.read_bytes(), before)

    def test_lock_rejects_second_builder(self):
        with temporary_db([raw_song()]) as target, build_lock(target):
            self.assertEqual(build_database(parse_args(["--db-path", str(target)])), 1)
