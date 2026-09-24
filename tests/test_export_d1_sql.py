import sqlite3
import unittest
from contextlib import closing
from unittest.mock import patch

from tests.helpers import temporary_db, raw_song
from tools.export_d1_sql import export_atomic, PUBLICATION_KEY
from vocaloid_title_search.database import load_statistics
import json


class ExportD1SqlTests(unittest.TestCase):
    def test_failed_export_keeps_previous_sql(self):
        with temporary_db([raw_song()]) as db_path, closing(sqlite3.connect(db_path)) as connection:
            output = db_path.with_suffix('.sql')
            output.write_text('previous SQL')
            with patch('tools.export_d1_sql.write_export', side_effect=RuntimeError('disk failure')):
                with self.assertRaises(RuntimeError):
                    export_atomic(connection, output)
            self.assertEqual(output.read_text(), 'previous SQL')
            self.assertEqual(list(output.parent.glob('.songs.sql.*')), [])

    def test_export_round_trip_preserves_data(self):
        with temporary_db([raw_song("引用'と改行\nの曲")]) as db_path, closing(sqlite3.connect(db_path)) as source:
            output = db_path.with_suffix('.sql')
            export_atomic(source, output)
            with closing(sqlite3.connect(':memory:')) as target:
                target.executescript(output.read_text())
                for table in ('songs', 'metadata', 'song_details', 'song_credit_people'):
                    self.assertEqual(source.execute(f'SELECT * FROM {table}').fetchall(),
                                     target.execute(f'SELECT * FROM {table}').fetchall())

    def test_publication_is_last_and_absent_during_replacement(self):
        with temporary_db([raw_song()]) as path, closing(sqlite3.connect(path)) as source:
            output = path.with_suffix('.sql')
            export_atomic(source, output, publish=True)
            sql = output.read_text()
            with closing(sqlite3.connect(':memory:')) as target:
                target.executescript(sql)
                record = json.loads(target.execute("SELECT value FROM metadata WHERE key=?", (PUBLICATION_KEY,)).fetchone()[0])
                self.assertEqual(record['statistics'], load_statistics(path))
                self.assertEqual(record['metadata']['song_count'], '1')
                # Apply each complete statement, including multiline detail JSON.
                statement = ''
                statements = []
                for line in sql.splitlines(keepends=True):
                    statement += line
                    if sqlite3.complete_statement(statement):
                        statements.append(statement)
                        statement = ''
                for statement in statements[:-1]:
                    target.executescript(statement)
                    exists = target.execute("SELECT 1 FROM sqlite_master WHERE name='metadata'").fetchone()
                    if exists:
                        self.assertIsNone(target.execute("SELECT value FROM metadata WHERE key=?", (PUBLICATION_KEY,)).fetchone())
                target.executescript(statements[-1])
                self.assertEqual(json.loads(target.execute("SELECT value FROM metadata WHERE key=?", (PUBLICATION_KEY,)).fetchone()[0]), record)
                rollback = path.with_suffix('.rollback.sql')
                export_atomic(target, rollback)
                self.assertEqual(rollback.read_text().splitlines()[-1], sql.splitlines()[-1])
            # A fresh release always gets a new revision, even with identical metadata timestamps.
            export_atomic(source, output, publish=True)
            self.assertNotEqual(sql, output.read_text())

    def test_publication_refuses_incomplete_data(self):
        with temporary_db([raw_song()]) as path, closing(sqlite3.connect(path)) as source:
            source.execute('DELETE FROM song_details')
            with self.assertRaises(ValueError):
                export_atomic(source, path.with_suffix('.sql'), publish=True)
