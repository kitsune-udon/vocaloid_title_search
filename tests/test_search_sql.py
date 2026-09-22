"""Execute the actual Worker SQL in SQLite; fake D1 cannot validate SQL semantics."""
from contextlib import closing
import sqlite3
import unittest

from tests.helpers import raw_song, temporary_db
from tools.benchmark_search_sql import ROOT, WORKER, search_sql
from vocaloid_title_search.database import load_paged_titles, save_song_detail_entry, sql_order_by, sql_where_clause, title_search_filters


class SearchSqlTests(unittest.TestCase):
    def test_worker_and_python_search_preserve_composers_filters_and_paging(self):
        songs = [raw_song(title, f"https://w.atwiki.jp/hmiku/pages/{i + 1}.html")
                 for i, title in enumerate(("Alpha", "Beta", "Gamma", "Delta"))]
        with temporary_db(songs) as path:
            for song, composers, year in zip(songs, (["Zed", "Alice"], [], ["Alice"], ["Other"]), (2020, None, 2007, 2020)):
                save_song_detail_entry(path, song.url, {
                    "credits": {"composer": composers, "lyricist": ["Excluded"]},
                    "published_year": year,
                })
            all_rows, total = load_paged_titles(path, None, "popularity")
            self.assertEqual(total, 4)
            self.assertEqual({row.title: row.artist for row in all_rows},
                             {"Alpha": "Alice / Zed", "Beta": "", "Gamma": "Alice", "Delta": "Other"})
            source = (ROOT / WORKER).read_text()
            with closing(sqlite3.connect(path)) as connection:
                for sort in ("popularity", "title_length_asc", "title_length_desc", "published_year_asc", "published_year_desc"):
                    for length, composer, year in ((None, "", None), (5, "", None), (None, "alice", None), (None, "", 2020), (5, "Alice", 2007), (None, "missing", None)):
                        for offset in (0, 1, 10):
                            with self.subTest(sort=sort, length=length, composer=composer, year=year, offset=offset):
                                clauses, params = title_search_filters(length, None, composer, year)
                                sql = search_sql(source, sql_where_clause(clauses), sql_order_by(sort))
                                actual = connection.execute(sql, [*params, 2, offset]).fetchall()
                                rows, _ = load_paged_titles(path, length, sort, composer_query=composer, published_year=year, limit=2, offset=offset)
                                expected = [(r.title, r.title_length, r.artist, r.artist_note, r.url, r.popularity_score, r.popularity_label, r.published_year) for r in rows]
                                self.assertEqual(actual, expected)
