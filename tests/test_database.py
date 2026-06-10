import sqlite3
from contextlib import closing
import unittest

from tests.helpers import MELT_URL, store_composer_detail, popularity, raw_song, temporary_db
from vocaloid_title_search.database import (
    database_is_ready,
    ensure_database,
    load_statistics,
    load_song_detail,
    load_paged_titles,
    load_titles_by_length,
    rebuild_database,
    save_song_detail_entry,
)
from vocaloid_title_search.models import RawSong


class DatabaseReadinessTests(unittest.TestCase):
    def test_missing_database_is_not_ready(self) -> None:
        with temporary_db() as db_path:
            self.assertFalse(database_is_ready(db_path.with_name("missing.sqlite3")))

    def test_empty_database_is_not_ready(self) -> None:
        with temporary_db() as db_path:
            with closing(sqlite3.connect(db_path)) as connection:
                ensure_database(connection)
                connection.commit()

            self.assertFalse(database_is_ready(db_path))

    def test_rebuild_starts_with_no_song_details(self) -> None:
        with temporary_db() as db_path:
            kept_url = "https://w.atwiki.jp/hmiku/pages/82.html"
            dropped_url = "https://w.atwiki.jp/hmiku/pages/999.html"
            rebuild_database(
                db_path,
                [RawSong("メルト/ryo", kept_url), RawSong("削除曲", dropped_url)],
                {},
                "source",
            )

            self.assertIsNone(load_song_detail(db_path, kept_url))
            self.assertIsNone(load_song_detail(db_path, dropped_url))

    def test_search_reads_existing_database_readonly(self) -> None:
        with temporary_db([raw_song("メルト/ryo")]) as db_path:
            results = load_titles_by_length(db_path, 3, "popularity")

            self.assertEqual(results[0].title_length, 3)

    def test_search_filters_by_stored_composer_credit(self) -> None:
        with temporary_db() as db_path:
            melt_url = "https://w.atwiki.jp/hmiku/pages/82.html"
            other_url = "https://w.atwiki.jp/hmiku/pages/83.html"
            rebuild_database(
                db_path,
                [RawSong("メルト", melt_url), RawSong("テスト", other_url)],
                {},
                "source",
            )
            save_song_detail_entry(
                db_path,
                melt_url,
                {
                    "page_title": "メルト",
                    "source_url": melt_url,
                    "credits": {"composer": ["ryo"]},
                },
            )

            results = load_titles_by_length(db_path, 3, "popularity", composer_query="RYO")

            self.assertEqual([result.title for result in results], ["メルト"])

    def test_search_uses_stored_composer_when_artist_is_empty(self) -> None:
        with temporary_db([raw_song()]) as db_path:
            store_composer_detail(db_path, names=("ryo", "supercell"))

            results = load_titles_by_length(db_path, 3, "popularity")

            self.assertEqual(results[0].artist, "ryo / supercell")

    def test_search_can_filter_by_composer_without_title_length(self) -> None:
        with temporary_db() as db_path:
            melt_url = "https://w.atwiki.jp/hmiku/pages/82.html"
            other_url = "https://w.atwiki.jp/hmiku/pages/83.html"
            rebuild_database(
                db_path,
                [RawSong("メルト", melt_url), RawSong("テスト曲", other_url)],
                {},
                "source",
            )
            save_song_detail_entry(
                db_path,
                melt_url,
                {
                    "page_title": "メルト",
                    "source_url": melt_url,
                    "credits": {"composer": ["ryo"]},
                },
            )

            results = load_titles_by_length(db_path, None, "popularity", composer_query="ryo")

            self.assertEqual([result.title for result in results], ["メルト"])

    def test_search_sorts_by_title_length(self) -> None:
        with temporary_db() as db_path:
            short_url = "https://w.atwiki.jp/hmiku/pages/82.html"
            long_url = "https://w.atwiki.jp/hmiku/pages/83.html"
            rebuild_database(
                db_path,
                [RawSong("短曲", short_url), RawSong("長い曲名", long_url)],
                {},
                "source",
            )
            for url, title in ((short_url, "短曲"), (long_url, "長い曲名")):
                save_song_detail_entry(
                    db_path,
                    url,
                    {
                        "page_title": title,
                        "source_url": url,
                        "credits": {"composer": ["tester"]},
                    },
                )

            ascending = load_titles_by_length(db_path, None, "title_length_asc", composer_query="tester")
            descending = load_titles_by_length(db_path, None, "title_length_desc", composer_query="tester")

            self.assertEqual([result.title for result in ascending], ["短曲", "長い曲名"])
            self.assertEqual([result.title for result in descending], ["長い曲名", "短曲"])

    def test_search_prefers_stored_composer_over_song_artist(self) -> None:
        with temporary_db([raw_song("メルト/ryo")]) as db_path:
            store_composer_detail(db_path, names=("supercell",))

            results = load_titles_by_length(db_path, 3, "popularity")

            self.assertEqual(results[0].artist, "supercell")

    def test_rebuild_requires_details_to_be_saved_again_for_composer_index(self) -> None:
        with temporary_db([raw_song()]) as db_path:
            store_composer_detail(db_path, names=("supercell",))

            rebuild_database(db_path, [raw_song(url=MELT_URL)], {}, "source2")

            results = load_titles_by_length(db_path, 3, "popularity", composer_query="super")

            self.assertEqual(results, [])

    def test_rebuild_does_not_store_published_year_without_details(self) -> None:
        with temporary_db([raw_song()], publication_years={"メルト": 2007}) as db_path:
            rebuild_database(db_path, [raw_song(url=MELT_URL)], {}, "source2")

            results = load_titles_by_length(db_path, 3, "popularity")

            self.assertEqual(results, [])

    def test_save_song_detail_stores_published_year(self) -> None:
        with temporary_db([raw_song()]) as db_path:
            save_song_detail_entry(
                db_path,
                MELT_URL,
                {
                    "page_title": "メルト",
                    "source_url": MELT_URL,
                    "published_year": 2007,
                },
            )

            results = load_titles_by_length(db_path, 3, "popularity")

            self.assertEqual(results[0].published_year, 2007)

            with closing(sqlite3.connect(db_path)) as connection:
                song_columns = {
                    row[1]
                    for row in connection.execute("PRAGMA table_info(songs)").fetchall()
                }
                detail_year = connection.execute(
                    "SELECT published_year FROM song_details WHERE url = ?",
                    (MELT_URL,),
                ).fetchone()[0]

            self.assertNotIn("published_year", song_columns)
            self.assertEqual(detail_year, 2007)

    def test_rebuild_does_not_create_video_metadata_table(self) -> None:
        with temporary_db([raw_song("メルト/ryo")]) as db_path:
            with closing(sqlite3.connect(db_path)) as connection:
                row = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'video_metadata'"
                ).fetchone()

            self.assertIsNone(row)

    def test_search_filters_and_sorts_by_published_year(self) -> None:
        with temporary_db(
            [RawSong("新曲", "https://w.atwiki.jp/hmiku/pages/101.html"), RawSong("古曲", "https://w.atwiki.jp/hmiku/pages/102.html")],
            publication_years={"新曲": 2024, "古曲": 2008},
        ) as db_path:
            filtered = load_titles_by_length(db_path, None, "popularity", published_year=2024)
            ascending = load_titles_by_length(db_path, None, "published_year_asc")
            descending = load_titles_by_length(db_path, None, "published_year_desc")

            self.assertEqual([result.title for result in filtered], ["新曲"])
            self.assertEqual([result.title for result in ascending], ["古曲", "新曲"])
            self.assertEqual([result.title for result in descending], ["新曲", "古曲"])

    def test_paged_search_returns_total_and_requested_slice(self) -> None:
        with temporary_db(
            [
                RawSong("一曲", "https://w.atwiki.jp/hmiku/pages/201.html"),
                RawSong("二曲", "https://w.atwiki.jp/hmiku/pages/202.html"),
                RawSong("三曲", "https://w.atwiki.jp/hmiku/pages/203.html"),
            ],
        ) as db_path:
            results, total = load_paged_titles(db_path, None, "popularity", limit=2, offset=1)

            self.assertEqual(total, 3)
            self.assertEqual([result.title for result in results], ["二曲", "三曲"])

    def test_load_statistics_groups_search_dimensions(self) -> None:
        with temporary_db(
            [
                RawSong("メルト", "https://w.atwiki.jp/hmiku/pages/82.html"),
                RawSong("新曲", "https://w.atwiki.jp/hmiku/pages/101.html"),
                RawSong("長い曲名", "https://w.atwiki.jp/hmiku/pages/102.html"),
            ],
            {
                "メルト": popularity(1000, "テンミリオン達成曲", 1),
                "新曲": popularity(500, "殿堂入り", 2),
                "長い曲名": popularity(500, "殿堂入り", 3),
            },
            publication_years={"メルト": 2007, "新曲": 2024},
        ) as db_path:
            save_song_detail_entry(
                db_path,
                "https://w.atwiki.jp/hmiku/pages/82.html",
                {
                    "page_title": "メルト",
                    "source_url": "https://w.atwiki.jp/hmiku/pages/82.html",
                    "published_year": 2007,
                    "credits": {"composer": ["ryo"]},
                },
            )
            save_song_detail_entry(
                db_path,
                "https://w.atwiki.jp/hmiku/pages/101.html",
                {
                    "page_title": "新曲",
                    "source_url": "https://w.atwiki.jp/hmiku/pages/101.html",
                    "published_year": 2024,
                    "credits": {"composer": ["ryo"]},
                },
            )
            stats = load_statistics(db_path)

            self.assertEqual(stats["total_songs"], 3)
            self.assertEqual(stats["with_composer"], 2)
            self.assertEqual(stats["with_published_year"], 2)
            self.assertIn({"length": 3, "count": 1}, stats["by_title_length"])
            self.assertIn({"year": 2007, "count": 1}, stats["by_published_year"])
            self.assertIn({"label": "殿堂入り", "count": 2}, stats["by_popularity_label"])
            self.assertEqual(stats["top_composers"][0], {"name": "ryo", "count": 2})

    def test_song_detail_requires_existing_song_url(self) -> None:
        with temporary_db([raw_song("メルト/ryo")]) as db_path:
            with self.assertRaises(sqlite3.IntegrityError):
                save_song_detail_entry(
                    db_path,
                    "https://w.atwiki.jp/hmiku/pages/999.html",
                    {"page_title": "未登録", "source_url": "https://w.atwiki.jp/hmiku/pages/999.html"},
                )


if __name__ == "__main__":
    unittest.main()
