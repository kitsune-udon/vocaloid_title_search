"""Fetching and parsing helpers for Hatsune Miku Wiki tag pages."""

from __future__ import annotations

import html
import re
import unicodedata
import urllib.error
import urllib.parse
from html.parser import HTMLParser
from typing import Callable

from vocaloid_title_search.models import PopularityInfo, RawSong, is_song_entry
from vocaloid_title_search.http import fetch_text


DEFAULT_TAG_URL = "https://w.atwiki.jp/hmiku/tag/%E6%AE%BF%E5%A0%82%E5%85%A5%E3%82%8A"
SITE_ROOT_URL = "https://w.atwiki.jp"
USER_AGENT = "vocaloid-title-search/1.0"

POPULARITY_TAGS = [
    ("YouTube1億再生達成曲", 1200),
    ("テンミリオン達成曲", 1000),
    ("YouTubeテンミリオン達成曲", 950),
    ("ミリオン達成曲", 800),
    ("YouTubeミリオン達成曲", 750),
    ("殿堂入り", 100),
]
class TagResultParser(HTMLParser):
    """Extract song page titles from the tag-search result area."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_results = False
        self.in_link = False
        self.current_href = ""
        self.current_text: list[str] = []
        self.songs: list[RawSong] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if not self.in_results or tag != "a":
            return

        href = dict(attrs).get("href") or ""
        if re.search(r"/hmiku/pages/\d+\.html$", href):
            self.in_link = True
            self.current_href = href
            self.current_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or not self.in_link:
            return

        title = normalize_title("".join(self.current_text))
        if title:
            self.songs.append(
                RawSong(title, urllib.parse.urljoin(SITE_ROOT_URL, self.current_href))
            )
        self.in_link = False
        self.current_href = ""
        self.current_text = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if "タグ検索" in text:
            self.in_results = True
            return
        if self.in_results and ("関連タグ" in text or "人気のタグ" in text):
            self.in_results = False
            return
        if self.in_link:
            self.current_text.append(data)


class WikiClient:
    def __init__(self, timeout: float) -> None:
        self.timeout = timeout

    def fetch_songs(self, source_url: str, pages: int) -> list[RawSong]:
        first_html = self.fetch_html(page_url(source_url, 1))
        last_page = find_last_page(first_html) if pages == 0 else pages

        songs: list[RawSong] = []
        seen: set[str] = set()
        for page_number in range(1, last_page + 1):
            page_html = (
                first_html
                if page_number == 1
                else self.fetch_html(page_url(source_url, page_number))
            )
            for song in extract_songs(page_html):
                if is_song_entry(song.raw_title) and song.raw_title not in seen:
                    seen.add(song.raw_title)
                    songs.append(song)
        return songs

    def fetch_html(self, url: str) -> str:
        return fetch_text(url, timeout=self.timeout, user_agent=USER_AGENT)


def normalize_title(raw_title: str) -> str:
    return unicodedata.normalize("NFC", html.unescape(raw_title)).strip()


def page_url(base_url: str, page_number: int) -> str:
    if page_number <= 1:
        return base_url

    parts = urllib.parse.urlsplit(base_url)
    query = dict(urllib.parse.parse_qsl(parts.query, keep_blank_values=True))
    query["p"] = str(page_number)
    return urllib.parse.urlunsplit(
        parts._replace(query=urllib.parse.urlencode(query))
    )


def find_last_page(first_page_html: str) -> int:
    page_numbers = [int(value) for value in re.findall(r"[?&]p=(\d+)", first_page_html)]
    return max(page_numbers, default=1)


def extract_songs(page_html: str) -> list[RawSong]:
    parser = TagResultParser()
    parser.feed(page_html)
    return parser.songs


def tag_url(tag_name: str) -> str:
    return f"https://w.atwiki.jp/hmiku/tag/{urllib.parse.quote(tag_name)}"


def fetch_popularity(
    client: WikiClient,
    progress: Callable[[str], None] | None = None,
) -> tuple[dict[str, PopularityInfo], list[RawSong]]:
    popularity: dict[str, PopularityInfo] = {}
    popularity_songs: list[RawSong] = []
    seen_songs: set[str] = set()
    for label, score in POPULARITY_TAGS:
        if progress:
            progress(f"人気度タグ取得中: {label}")
        try:
            songs = client.fetch_songs(tag_url(label), pages=0)
        except (urllib.error.URLError, TimeoutError, OSError):
            continue
        for order, song in enumerate(songs, start=1):
            if song.raw_title not in seen_songs:
                seen_songs.add(song.raw_title)
                popularity_songs.append(song)

            current = popularity.get(song.raw_title)
            if current is None or score > current.score:
                popularity[song.raw_title] = PopularityInfo(score, label, order)
    return popularity, popularity_songs


def merge_unique_songs(*song_groups: list[RawSong]) -> list[RawSong]:
    merged: list[RawSong] = []
    seen: set[str] = set()
    for songs in song_groups:
        for song in songs:
            if song.raw_title not in seen:
                seen.add(song.raw_title)
                merged.append(song)
    return merged


def build_title_corpus(
    client: WikiClient,
    source_url: str,
    progress: Callable[[str], None] | None = None,
) -> tuple[list[RawSong], dict[str, PopularityInfo]]:
    if progress:
        progress("代表タグ取得中")
    source_songs = client.fetch_songs(source_url, pages=0)
    popularity_map, popularity_songs = fetch_popularity(client, progress=progress)
    songs = merge_unique_songs(source_songs, popularity_songs)
    return songs, popularity_map
