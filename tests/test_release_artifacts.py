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

    def test_incremental_metadata_update_and_restore(self):
        from tools.incremental_release import prepare_incremental
        with TemporaryDirectory() as directory, temporary_db([raw_song()]) as source:
            root = Path(directory)
            with closing(sqlite3.connect(source)) as connection:
                (root / 'remote-before.sql').write_text('\n'.join(connection.iterdump()))
                export_atomic(connection, root / 'rollback.sql')
                connection.execute("UPDATE song_details SET fetched_at='updated'")
                connection.commit()
            prepare(source, root, 'staging', 'test-database')
            prepare_incremental(root)
            self.assertNotIn('INSERT INTO "songs"', (root / 'new-vocaloid_titles.sql').read_text())
            rehearse(root)
            verify(root)

    def test_incremental_refuses_song_changes(self):
        from tools.incremental_release import prepare_incremental
        with TemporaryDirectory() as directory, temporary_db([raw_song()]) as source:
            root = Path(directory)
            with closing(sqlite3.connect(source)) as connection:
                (root / 'remote-before.sql').write_text('\n'.join(connection.iterdump()))
                export_atomic(connection, root / 'rollback.sql')
                connection.execute("UPDATE songs SET raw_title='different', title='different', title_length=9")
                connection.commit()
            prepare(source, root, 'staging', 'test-database')
            with self.assertRaisesRegex(ValueError, 'cannot change songs'):
                prepare_incremental(root)

    def test_rehearsal_rejects_wrong_forward_rows_even_with_valid_hashes(self):
        from tools.release_state import digest, save_manifest
        with TemporaryDirectory() as directory, temporary_db([raw_song()]) as source:
            root = Path(directory)
            prepare(source, root, "staging", "test-database")
            with closing(sqlite3.connect(source)) as connection:
                (root / "remote-before.sql").write_text("\n".join(connection.iterdump()))
                export_atomic(connection, root / "rollback.sql")
            sql = root / "new-vocaloid_titles.sql"
            with sql.open("a") as output:
                output.write("UPDATE songs SET title='incorrect export';\n")
            manifest = json.loads((root / "manifest.json").read_text())
            manifest["artifacts"][sql.name] = digest(sql)
            save_manifest(root, manifest)
            with self.assertRaisesRegex(ValueError, "forward rehearsal differs"):
                rehearse(root)
            with self.assertRaisesRegex(ValueError, "rehearsal is required"):
                verify(root)

    def test_rehearsal_rejects_missing_publication(self):
        from tools.release_state import digest, save_manifest
        with TemporaryDirectory() as directory, temporary_db([raw_song()]) as source:
            root = Path(directory)
            prepare(source, root, "staging", "test-database")
            with closing(sqlite3.connect(source)) as connection:
                (root / "remote-before.sql").write_text("\n".join(connection.iterdump()))
                export_atomic(connection, root / "rollback.sql")
            sql = root / "new-vocaloid_titles.sql"
            with sql.open("a") as output:
                output.write("DELETE FROM metadata WHERE key='api_publication_v1';\n")
            manifest = json.loads((root / "manifest.json").read_text())
            manifest["artifacts"][sql.name] = digest(sql)
            save_manifest(root, manifest)
            with self.assertRaisesRegex(ValueError, "no publication record"):
                rehearse(root)

    def test_incremental_rollback_restores_every_interrupted_prefix(self):
        from tools.incremental_release import statements
        from tools.release_state import table_state
        with temporary_db([raw_song()]) as source:
            for old_index, new_index in ((False, True), (True, False), (True, True)):
                with self.subTest(old_index=old_index, new_index=new_index), closing(sqlite3.connect(':memory:')) as old, closing(sqlite3.connect(':memory:')) as new:
                    with closing(sqlite3.connect(source)) as origin:
                        origin.backup(old)
                        origin.backup(new)
                    if not old_index:
                        old.execute('DROP INDEX idx_songs_order')
                    if not new_index:
                        new.execute('DROP INDEX idx_songs_order')
                    new.execute("UPDATE song_details SET fetched_at='new time'")
                    new.execute("INSERT INTO metadata VALUES ('refresh_test', 'new')")
                    new.commit()
                    old.commit()
                    forward, rollback = statements(old, new), statements(new, old)
                    commands = []
                    statement = ''
                    for line in forward.splitlines(keepends=True):
                        statement += line
                        if sqlite3.complete_statement(statement):
                            commands.append(statement)
                            statement = ''
                    self.assertFalse(statement.strip())
                    original = table_state(old)
                    for stop in range(len(commands) + 1):
                        with closing(sqlite3.connect(':memory:')) as interrupted:
                            old.backup(interrupted)
                            interrupted.executescript('\n'.join(commands[:stop]))
                            interrupted.executescript(rollback)
                            self.assertEqual(table_state(interrupted), original, f'interrupted after {stop} statements')
