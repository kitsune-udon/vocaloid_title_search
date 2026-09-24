import unittest
import urllib.error
from unittest.mock import patch

from vocaloid_title_search.models import RawSong
from vocaloid_title_search.wiki import POPULARITY_TAGS, fetch_popularity, WikiClient


def tag_page(body, current=1, last=1):
    import re
    links = re.findall(r'<a href="/hmiku/pages/[^>]+>.*?</a>', body)
    rows = ''.join('<li>'+link+'</li>' for link in links)
    navigation = '<div class="atwiki-pagination-wrap"><span>['+str(current)+']</span>'
    navigation += ''.join(f'<a href="?p={n}">{n}</a>' for n in range(1,last+1) if n != current)+'</div>'
    return '<div class="cmd_tag"><ul class="atwiki-page-list">'+rows+'</ul>'+navigation+'</div>'


class PopularityTagsTests(unittest.TestCase):
    def test_empty_successful_page_is_not_a_valid_corpus(self):
        good = 'タグ検索 <a href="/hmiku/pages/82.html">メルト</a>'
        cases = [("<html>maintenance</html>",),
                 (tag_page('タグ検索 <a href="/hmiku/pages/1.html">曲一覧</a>'),),
                 (tag_page(good,current=1,last=2), '<html>maintenance</html>')]
        for pages in cases:
            with self.subTest(pages=pages), patch.object(WikiClient, "fetch_html", side_effect=pages):
                with self.assertRaisesRegex(urllib.error.URLError, "no song entries"):
                    WikiClient(timeout=1).fetch_songs("https://example.test/tag", pages=0)

    def test_valid_paginated_corpus_preserves_order(self):
        pages = ['タグ検索 <a href="/hmiku/pages/82.html">メルト</a><a href="?p=2">2</a>',
                 'タグ検索 <a href="/hmiku/pages/2.html">別曲</a>']
        with patch.object(WikiClient, "fetch_html", side_effect=[tag_page(p,current=n,last=2) for n,p in enumerate(pages,1)]):
            songs = WikiClient(timeout=1).fetch_songs("https://example.test/tag", pages=0)
        self.assertEqual([song.raw_title for song in songs], ["メルト", "別曲"])

    def test_repeated_or_overlapping_pages_are_not_a_complete_corpus(self):
        first = 'タグ検索 <a href="/hmiku/pages/82.html">メルト</a><a href="?p=2">2</a>'
        for second in (first, first + '<a href="/hmiku/pages/2.html">別曲</a>'):
            with self.subTest(second=second), patch.object(WikiClient, "fetch_html", side_effect=[tag_page(first,current=1,last=2), tag_page(second,current=2,last=2)]):
                with self.assertRaisesRegex(urllib.error.URLError, "duplicate song entries|partial tag page"):
                    WikiClient(timeout=1).fetch_songs("https://example.test/tag", pages=0)

    def test_duplicate_links_within_page_are_rejected(self):
        page = 'タグ検索 <a href="/hmiku/pages/82.html">メルト</a><a href="/hmiku/pages/82.html">別名</a>'
        with patch.object(WikiClient, "fetch_html", return_value=tag_page(page)):
            with self.assertRaisesRegex(urllib.error.URLError, "duplicate song entries|partial tag page"):
                WikiClient(timeout=1).fetch_songs("https://example.test/tag", pages=0)

    def test_partial_middle_page_and_pagination_changes_are_rejected(self):
        first = tag_page('<a href="/hmiku/pages/10.html">曲甲</a><a href="/hmiku/pages/11.html">曲乙</a>',1,3)
        second = '<a href="/hmiku/pages/12.html">曲丙</a><a href="/hmiku/pages/13.html">曲丁</a>'
        for body, expected in ((tag_page('<a href="/hmiku/pages/12.html">曲丙</a>',2,3),'partial tag page'),
                               (tag_page(second,1,3),'pagination changed'),
                               (tag_page(second,2,4),'pagination changed')):
            with self.subTest(expected=expected), patch.object(WikiClient,'fetch_html',side_effect=[first,body]):
                with self.assertRaisesRegex(urllib.error.URLError,expected):
                    WikiClient(1).fetch_songs('https://example.test/tag',0)

    def test_unrelated_navigation_is_ignored_and_bad_rows_are_rejected(self):
        from vocaloid_title_search.wiki import validated_tag_page
        page = tag_page('<a href="/hmiku/pages/10.html">曲甲</a>')
        songs,current,last = validated_tag_page('<a href="?p=999">navigation</a>'+page)
        self.assertEqual((len(songs),current,last),(1,1,1))
        with self.assertRaisesRegex(urllib.error.URLError,'malformed tag entry'):
            validated_tag_page(page.replace('/hmiku/pages/10.html','https://example.test/hmiku/pages/10.html'))

    def test_youtube_hundred_million_tag_is_highest_priority(self) -> None:
        self.assertEqual(POPULARITY_TAGS[0], ("YouTube1億再生達成曲", 1200))
        scores = [score for _, score in POPULARITY_TAGS]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_popularity_fetch_refuses_incomplete_tags(self) -> None:
        class Client:
            def __init__(self) -> None:
                self.calls = 0

            def fetch_songs(self, source_url: str, pages: int) -> list[RawSong]:
                self.calls += 1
                if self.calls == 1:
                    raise urllib.error.URLError("temporary failure")
                return [RawSong(f"曲{self.calls}", f"https://example.test/{self.calls}")]

        with self.assertRaisesRegex(urllib.error.URLError, "popularity tag fetch failed"):
            fetch_popularity(Client())


if __name__ == "__main__":
    unittest.main()
