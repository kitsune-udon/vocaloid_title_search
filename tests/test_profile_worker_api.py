import unittest
from unittest.mock import patch
import urllib.error

from tools.profile_worker_api import ProfileRequest, measure_request, representative_requests


class ProfileWorkerApiTests(unittest.TestCase):
    def test_errors_are_counted_and_measurement_continues(self):
        with patch("tools.profile_worker_api.fetch_once", side_effect=[(200, 10), urllib.error.URLError("offline"), (503, 0)]), patch("tools.profile_worker_api.time.perf_counter", side_effect=[0, .1, 1, 1.2, 2, 2.3]):
            result = measure_request("http://example.test", ProfileRequest("test", "/"), timeout=1, repeat=3)
        self.assertEqual(result["errors"], 2)
        self.assertEqual(result["p95_ms"], 300)
        self.assertEqual(result["median_ms"], 200)
        self.assertEqual(result["statuses"], {"200": 1, "0": 1, "503": 1})

    def test_representative_requests_cover_search_variants_and_stats(self) -> None:
        requests = representative_requests()
        names = {request.name for request in requests}

        self.assertIn("stats", names)
        self.assertIn("search_length", names)
        self.assertIn("search_composer", names)
        self.assertIn("search_year", names)
        self.assertIn("search_tag", names)
        self.assertIn("search_page_size_200", names)
        self.assertIn("song_detail", names)


if __name__ == "__main__":
    unittest.main()
