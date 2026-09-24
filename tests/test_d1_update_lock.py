from contextlib import closing
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from tools.d1_update_lock import CREATE, statement

FIRST = '00000000-0000-4000-8000-000000000001'
SECOND = '00000000-0000-4000-8000-000000000002'


class D1UpdateLockTests(unittest.TestCase):
    def test_independent_connections_cannot_take_or_release_an_owned_lock(self):
        with TemporaryDirectory() as directory:
            database = Path(directory) / 'lock.sqlite3'
            with closing(sqlite3.connect(database)) as first, closing(sqlite3.connect(database)) as second:
                first.execute(CREATE)
                self.assertEqual(first.execute(statement('acquire', FIRST)).fetchall(), [(FIRST,)])
                first.commit()
                with self.assertRaises(sqlite3.IntegrityError):
                    second.execute(statement('acquire', SECOND))
                second.rollback()
                self.assertEqual(second.execute(statement('release', SECOND)).fetchall(), [])
                second.commit()
            # Closing the owning process does not expire or unlock a potentially partial update.
            with closing(sqlite3.connect(database)) as recovery:
                with self.assertRaises(sqlite3.IntegrityError):
                    recovery.execute(statement('acquire', SECOND))
                recovery.rollback()
                self.assertEqual(recovery.execute(statement('release', FIRST)).fetchall(), [(FIRST,)])
                recovery.commit()
                self.assertEqual(recovery.execute(statement('acquire', SECOND)).fetchall(), [(SECOND,)])

    def test_application_export_and_rollback_preserve_lock_table(self):
        from tests.helpers import temporary_db, raw_song
        from tools.export_d1_sql import export_atomic
        with TemporaryDirectory() as directory, temporary_db([raw_song()]) as source:
            with closing(sqlite3.connect(source)) as original, closing(sqlite3.connect(':memory:')) as target:
                target.execute(CREATE)
                target.execute(statement('acquire', FIRST)).fetchall()
                target.commit()
                for publish in (True, False):
                    sql = Path(directory) / 'application.sql'
                    export_atomic(original, sql, publish=publish)
                    target.executescript(sql.read_text())
                    self.assertEqual(target.execute('SELECT owner FROM _vts_update_lock').fetchall(), [(FIRST,)])

    def test_sql_rejects_invalid_owner_and_unknown_actions(self):
        for owner in ('', "x'; DROP TABLE songs; --", 'not-a-uuid'):
            with self.assertRaises(ValueError):
                statement('acquire', owner)
        with self.assertRaises(ValueError):
            statement('renew', FIRST)
