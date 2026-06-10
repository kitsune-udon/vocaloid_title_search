import unittest

from tools.profile_worker_api import representative_requests


class ProfileWorkerApiTests(unittest.TestCase):
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
