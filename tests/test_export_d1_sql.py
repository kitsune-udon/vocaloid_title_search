import sqlite3
import unittest
from contextlib import closing
from unittest.mock import patch

from tests.helpers import temporary_db, raw_song
from tools.export_d1_sql import export_atomic


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
