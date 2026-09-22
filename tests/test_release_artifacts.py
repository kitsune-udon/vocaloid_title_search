from contextlib import closing
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from tests.helpers import raw_song, temporary_db
from tools.export_d1_sql import export_atomic
from tools.release_artifacts import prepare, rehearse, verify


class ReleaseArtifactTests(unittest.TestCase):
    def test_snapshot_restore_and_tamper_detection(self):
        with TemporaryDirectory() as directory, temporary_db([raw_song()]) as source:
            root = Path(directory)
            prepare(source, root, "staging", "test-database")
            with closing(sqlite3.connect(source)) as connection:
                (root / "remote-before.sql").write_text("\n".join(connection.iterdump()))
                export_atomic(connection, root / "rollback.sql")
                connection.execute("UPDATE songs SET title='changed after snapshot'")
                connection.commit()
            rehearse(root)
            verify(root)
            manifest = json.loads((root / "manifest.json").read_text())
            self.assertTrue(manifest["rollback_verified"])
            self.assertIn("quality-comparison.json", manifest["artifacts"])
            with closing(sqlite3.connect(root / "new-vocaloid_titles.sqlite3")) as snapshot:
                self.assertEqual(snapshot.execute("SELECT title FROM songs").fetchone()[0], "メルト")
            with (root / "new-vocaloid_titles.sql").open("a") as output:
                output.write("-- tampered")
            with self.assertRaisesRegex(ValueError, "changed after validation"):
                verify(root)

    def test_rehearsal_rejects_incomplete_restore(self):
        with TemporaryDirectory() as directory, temporary_db([raw_song()]) as source:
            root = Path(directory)
            prepare(source, root, "staging", "test-database")
            with closing(sqlite3.connect(source)) as connection:
                (root / "remote-before.sql").write_text("\n".join(connection.iterdump()))
            (root / "rollback.sql").write_text("DELETE FROM songs;")
            with self.assertRaisesRegex(ValueError, "restore application tables"):
                rehearse(root)
