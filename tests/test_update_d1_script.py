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


if __name__ == "__main__":
    unittest.main()
