from contextlib import closing
import subprocess
import unittest
from pathlib import Path

from tests.helpers import MELT_URL, raw_song, temporary_db
from vocaloid_title_search.database import save_song_detail_entry


ROOT_DIR = Path(__file__).resolve().parent.parent


class UpdateD1ScriptTests(unittest.TestCase):
    def test_dry_run_validates_database_before_export(self) -> None:
        with temporary_db([raw_song()]) as db_path:
            save_song_detail_entry(
                db_path,
                MELT_URL,
                {
                    "page_title": "メルト",
                    "source_url": MELT_URL,
                    "published_year": 2007,
                    "credits": {"composer": ["ryo"]},
                },
            )

            result = subprocess.run(
                [
                    str(ROOT_DIR / "tools/update_d1.sh"),
                    "--env",
                    "staging",
                    "--db-path",
                    str(db_path),
                    "--dry-run",
                    "--skip-smoke-checks",
                ],
                cwd=ROOT_DIR,
                check=False,
                text=True,
                capture_output=True,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("[update-d1] Operation summary", result.stdout)
        self.assertIn("Target: staging", result.stdout)
        self.assertIn("Changes: D1 data in", result.stdout)
        self.assertIn("Unchanged: SQLite source DB, Pages artifact, Worker script, Terraform resources", result.stdout)
        self.assertIn("Smoke checks: skipped", result.stdout)
        validate_index = result.stdout.find("vocaloid_title_search.cli.validate_db")
        export_index = result.stdout.find("tools/export_d1_sql.py")
        self.assertGreaterEqual(validate_index, 0, result.stdout)
        self.assertGreater(export_index, validate_index, result.stdout)


class UpdateD1SafetyTests(unittest.TestCase):
    def run_update(self, root, db_path, *, backup_fails=False, corrupt_backup=False, empty_backup=False, import_fails=False, base_url=None):
        import os
        import json
        worker = root / "worker"
        binary = worker / "node_modules/.bin/wrangler"
        binary.parent.mkdir(parents=True)
        binary.write_text('''#!/usr/bin/env python3
import os, sys, json, shutil
from pathlib import Path
args = sys.argv[1:]
with open(os.environ["TEST_CALLS"], "a") as output:
    output.write(json.dumps(args) + "\\n")
if args[1] == "execute" and "--command" in args:
    import sqlite3
    from contextlib import closing
    with closing(sqlite3.connect(os.environ["TEST_LOCK_DB"])) as connection, connection:
        cursor = connection.execute(args[args.index("--command") + 1])
        rows = [dict(zip([item[0] for item in cursor.description], row)) for row in cursor.fetchall()] if cursor.description else []
    print(json.dumps([{"success":True,"results":rows}]))
    sys.exit(0)
if args[1] == "execute" and "--file" in args and os.environ.get("TEST_IMPORT_FAIL") == "1":
    sys.exit(1)
if args[1] == "export":
    if os.environ.get("TEST_BACKUP_FAIL") == "1":
        sys.exit(1)
    shutil.copyfile(os.environ["TEST_REMOTE_SQL"], args[args.index("--output") + 1])
''')
        binary.chmod(0o755)
        import sqlite3
        from contextlib import closing
        with closing(sqlite3.connect(db_path)) as connection:
            (root / "remote.sql").write_text("\n".join(connection.iterdump()))
        if empty_backup:
            (root / "remote.sql").write_text("BEGIN TRANSACTION; COMMIT;")
        if corrupt_backup:
            (root / "remote.sql").write_text("invalid SQL")
        calls = root / "calls.jsonl"
        env = {**os.environ, "VOCALOID_ENV_FILE": "/dev/null", "VOCALOID_WORKER_DIR": str(worker),
               "TEST_CALLS": str(calls), "TEST_LOCK_DB": str(root / "lock.sqlite3"), "TEST_REMOTE_SQL": str(root / "remote.sql"),
               "TEST_BACKUP_FAIL": "1" if backup_fails else "0", "TEST_IMPORT_FAIL": "1" if import_fails else "0"}
        result = subprocess.run([
            str(ROOT_DIR / "tools/update_d1.sh"), "--env", "staging", "--yes",
            *(["--base-url", base_url] if base_url else ["--skip-smoke-checks"]), "--database", "test-database", "--db-path", str(db_path),
            "--sql-output", str(root / "new.sql"), "--backup-dir", str(root / "backups"),
        ], cwd=ROOT_DIR, env=env, text=True, capture_output=True)
        recorded = [json.loads(line) for line in calls.read_text().splitlines()] if calls.exists() else []
        return result, recorded

    def test_remote_snapshot_precedes_import_and_can_restore_over_existing_tables(self):
        import sqlite3
        from contextlib import closing
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory, temporary_db([raw_song()]) as db_path:
            root = Path(directory)
            result, calls = self.run_update(root, db_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual([call[1] for call in calls], ["execute", "execute", "export", "execute"])
            rollback = next((root / "backups").glob("*/rollback.sql"))
            with closing(sqlite3.connect(":memory:")) as connection:
                connection.executescript((root / "new.sql").read_text())
                connection.execute("UPDATE songs SET title = 'changed'")
                connection.executescript(rollback.read_text())
                self.assertEqual(connection.execute("SELECT title FROM songs").fetchone()[0], "メルト")

    def test_import_failure_is_recorded_with_restore_command(self):
        import json
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory, temporary_db([raw_song()]) as db_path:
            root = Path(directory)
            result, _ = self.run_update(root, db_path, import_fails=True)
            self.assertNotEqual(result.returncode, 0)
            manifest = json.loads(next((root / "backups").glob("*/manifest.json")).read_text())
            self.assertEqual(manifest["status"], "import_failed")
            self.assertIn("Restore the verified snapshot", result.stderr)

    def test_concurrent_update_is_rejected_before_remote_calls(self):
        import fcntl
        import hashlib
        from tempfile import TemporaryDirectory
        lock = ROOT_DIR / "release/locks" / (hashlib.sha256(b"test-database").hexdigest() + ".lock")
        lock.parent.mkdir(parents=True, exist_ok=True)
        with lock.open("a") as held, TemporaryDirectory() as directory, temporary_db([raw_song()]) as db_path:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result, calls = self.run_update(Path(directory), db_path)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Another update", result.stderr)
            self.assertEqual(calls, [])

    def test_failed_snapshot_prevents_import(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory, temporary_db([raw_song()]) as db_path:
            result, calls = self.run_update(Path(directory), db_path, backup_fails=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual([call[1] for call in calls], ["execute", "execute", "export"])

    def test_empty_remote_database_can_be_initialized_and_rolled_back(self):
        import sqlite3
        from contextlib import closing
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory, temporary_db([raw_song()]) as db_path:
            root = Path(directory)
            result, calls = self.run_update(root, db_path, empty_backup=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            rollback = next((root / "backups").glob("*/rollback.sql"))
            with closing(sqlite3.connect(":memory:")) as connection:
                connection.executescript((root / "new.sql").read_text())
                connection.executescript(rollback.read_text())
                self.assertEqual(connection.execute("SELECT count(*) FROM sqlite_master WHERE name = 'songs'").fetchone()[0], 0)

    def test_invalid_snapshot_prevents_import(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory, temporary_db([raw_song()]) as db_path:
            result, calls = self.run_update(Path(directory), db_path, corrupt_backup=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual([call[1] for call in calls], ["execute", "execute", "export"])

    def test_other_host_owner_prevents_remote_snapshot(self):
        import sqlite3
        from tempfile import TemporaryDirectory
        from tools.d1_update_lock import CREATE, statement
        owner = '00000000-0000-4000-8000-000000000001'
        with TemporaryDirectory() as directory, temporary_db([raw_song()]) as db_path:
            root = Path(directory)
            with closing(sqlite3.connect(root / 'lock.sqlite3')) as connection, connection:
                connection.execute(CREATE)
                connection.execute(statement('acquire', owner)).fetchall()
            result, calls = self.run_update(root, db_path)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(any(call[1] == 'export' or '--file' in call for call in calls))
            with closing(sqlite3.connect(root / 'lock.sqlite3')) as connection, connection:
                self.assertEqual(connection.execute('SELECT owner FROM _vts_update_lock').fetchall(), [(owner,)])

    def test_import_failure_and_skipped_smoke_retain_owner(self):
        import sqlite3
        from tempfile import TemporaryDirectory
        for import_fails in (False, True):
            with self.subTest(import_fails=import_fails), TemporaryDirectory() as directory, temporary_db([raw_song()]) as db_path:
                root = Path(directory)
                result, _ = self.run_update(root, db_path, import_fails=import_fails)
                owner = next((root / 'backups').glob('*/remote-lock-owner.txt')).read_text().strip()
                with closing(sqlite3.connect(root / 'lock.sqlite3')) as connection, connection:
                    self.assertEqual(connection.execute('SELECT owner FROM _vts_update_lock').fetchall(), [(owner,)])
                self.assertIn('Inspect the update', result.stderr)

    def test_verified_smoke_releases_owner_after_import(self):
        import json
        import sqlite3
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from tempfile import TemporaryDirectory
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                path = self.path.split('?')[0]
                payload = {'/health': {'ok':True,'database_ready':True},
                    '/api/metadata': {'schema_version':'7','song_count':'1'},
                    '/api/popularity-labels': {'labels':['test']},
                    '/api/search': {'total':1,'results':[{'title':'test'}]},
                    '/api/song-detail': {'page_title':'メルト','videos':{}},
                    '/api/stats': {'total_songs':1}}[path]
                self.send_response(200); self.end_headers()
                self.wfile.write(json.dumps(payload).encode())
            def log_message(self, *args): pass
        server = ThreadingHTTPServer(('127.0.0.1',0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            with TemporaryDirectory() as directory, temporary_db([raw_song()]) as db_path:
                root = Path(directory)
                result, calls = self.run_update(root, db_path, base_url=f'http://127.0.0.1:{server.server_port}')
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertIn('DELETE FROM _vts_update_lock', calls[-1][calls[-1].index('--command')+1])
                with closing(sqlite3.connect(root/'lock.sqlite3')) as connection, connection:
                    self.assertEqual(connection.execute('SELECT * FROM _vts_update_lock').fetchall(),[])
        finally:
            server.shutdown(); server.server_close(); thread.join()

    def test_missing_video_refresh_prevents_any_remote_call(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory, temporary_db([raw_song()]) as db_path:
            save_song_detail_entry(db_path, MELT_URL, {"videos": {"youtube": [{"id": "video"}]}})
            result, calls = self.run_update(Path(directory), db_path)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
