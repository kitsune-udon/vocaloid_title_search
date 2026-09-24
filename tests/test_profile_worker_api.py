import unittest
from unittest.mock import patch, MagicMock
import urllib.error

from tools.profile_worker_api import ProfileRequest, measure_request, representative_requests, validate_target, main


class ProfileWorkerApiTests(unittest.TestCase):
    def test_errors_stop_further_measurement(self):
        with patch("tools.profile_worker_api.fetch_once", side_effect=[(200, 10, 7), urllib.error.URLError("offline"), (503, 0, None)]), patch("tools.profile_worker_api.time.perf_counter", side_effect=[0, .1, 1, 1.2, 2, 2.3]):
            result = measure_request("http://example.test", ProfileRequest("test", "/"), timeout=1, repeat=3)
        self.assertEqual(result["errors"], 1)
        self.assertEqual(result["p95_ms"], 200)
        self.assertEqual(result["median_ms"], 150)
        self.assertEqual(result["statuses"], {"200": 1, "0": 1})

    def test_only_loopback_targets_allow_repeated_measurements(self):
        for url in ("https://example.com", "http://127.0.0.1.example.com"):
            with self.assertRaises(SystemExit):
                validate_target(url, 2)
            validate_target(url, 1)
        for url in ("http://127.0.0.1:8789", "http://localhost:8789", "http://[::1]:8789"):
            validate_target(url, 20)

    def test_read_counts_are_recorded_and_summed(self):
        with patch("tools.profile_worker_api.fetch_once", side_effect=[(200, 10, 7), (200, 10, 1)]):
            result = measure_request("http://localhost", ProfileRequest("test", "/"), timeout=1, repeat=2)
        self.assertEqual(result["rows_read"], [7, 1])
        self.assertEqual(result["total_rows_read"], 8)

    def test_unready_or_invalid_health_stops_repeats(self):
        for body in (b'{"database_ready":false}', b'<html>not an API</html>', b'[]'):
            with self.subTest(body=body):
                response = MagicMock()
                response.__enter__.return_value = response
                response.status = 200
                response.read.return_value = body
                with patch("tools.profile_worker_api.urllib.request.urlopen", return_value=response) as fetch:
                    result = measure_request("http://localhost", ProfileRequest("health", "/health"), timeout=1, repeat=3)
                self.assertEqual(result["errors"], 1)
                self.assertEqual(result["samples"], 1)
                fetch.assert_called_once()

    def test_first_failure_stops_remaining_endpoints(self):
        with patch("sys.argv", ["profile", "--base-url", "https://example.com"]), \
             patch("tools.profile_worker_api.fetch_once", return_value=(503, 0, None)) as fetch, \
             patch("builtins.print"):
            self.assertEqual(main(), 1)
        fetch.assert_called_once()

    def test_unknown_read_count_is_not_zero(self):
        with patch("tools.profile_worker_api.fetch_once", return_value=(200, 10, None)):
            result = measure_request("http://localhost", ProfileRequest("test", "/"), timeout=1, repeat=1)
        self.assertIsNone(result["total_rows_read"])

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
