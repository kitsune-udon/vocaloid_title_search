import unittest
import urllib.error

from vocaloid_title_search.models import RawSong
from vocaloid_title_search.wiki import POPULARITY_TAGS, fetch_popularity


class PopularityTagsTests(unittest.TestCase):
    def test_youtube_hundred_million_tag_is_highest_priority(self) -> None:
        self.assertEqual(POPULARITY_TAGS[0], ("YouTube1億再生達成曲", 1200))
        scores = [score for _, score in POPULARITY_TAGS]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_popularity_fetch_continues_when_one_tag_fails(self) -> None:
        class Client:
            def __init__(self) -> None:
                self.calls = 0

            def fetch_songs(self, source_url: str, pages: int) -> list[RawSong]:
                self.calls += 1
                if self.calls == 1:
                    raise urllib.error.URLError("temporary failure")
                return [RawSong(f"曲{self.calls}", f"https://example.test/{self.calls}")]

        popularity, songs = fetch_popularity(Client())

        self.assertTrue(songs)
        self.assertTrue(popularity)


if __name__ == "__main__":
    unittest.main()
