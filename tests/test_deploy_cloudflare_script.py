import subprocess
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent


class DeployCloudflareScriptTests(unittest.TestCase):
    def test_dry_run_runs_smoke_check_when_base_url_is_set(self) -> None:
        result = subprocess.run(
            [
                str(ROOT_DIR / "tools/deploy_cloudflare.sh"),
                "--env",
                "staging",
                "--base-url",
                "https://vocaloid-title-search.example.com",
                "--skip-build",
                "--skip-pages",
                "--skip-worker",
                "--dry-run",
            ],
            cwd=ROOT_DIR,
            check=False,
            text=True,
            capture_output=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("[deploy-cloudflare] Operation summary", result.stdout)
        self.assertIn("Target: staging", result.stdout)
        self.assertIn("Changes: none", result.stdout)
        self.assertIn("Unchanged: D1 data, Terraform resources", result.stdout)
        self.assertIn("Smoke checks: https://vocaloid-title-search.example.com", result.stdout)
        self.assertIn("Running staging smoke checks", result.stdout)
        self.assertIn("tools/check_worker_api.py", result.stdout)


if __name__ == "__main__":
    unittest.main()
