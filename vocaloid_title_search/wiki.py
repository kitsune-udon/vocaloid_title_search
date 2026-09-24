"""Fetching and parsing helpers for Hatsune Miku Wiki tag pages."""

from __future__ import annotations

import html
import re
import unicodedata
import urllib.error
import urllib.parse
from bs4 import BeautifulSoup
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
class WikiClient:
    def __init__(self, timeout: float) -> None:
        self.timeout = timeout

    def fetch_songs(self, source_url: str, pages: int) -> list[RawSong]:
        first_html = self.fetch_html(page_url(source_url, 1))
        first_entries, first_current, source_last = validated_tag_page(first_html)
        last_page = source_last if pages == 0 else min(pages, source_last)
        expected_page_size = len(first_entries)

        songs: list[RawSong] = []
        seen: set[str] = set()
        seen_urls: set[str] = set()
        for page_number in range(1, last_page + 1):
            page_html = (
                first_html
                if page_number == 1
                else self.fetch_html(page_url(source_url, page_number))
            )
            entries, current, declared_last = (first_entries, first_current, source_last) if page_number == 1 else validated_tag_page(page_html)
            if current != page_number or declared_last != source_last:
                raise urllib.error.URLError(f"pagination changed on tag page {page_number}")
            if len(entries) > expected_page_size or (page_number < source_last and len(entries) != expected_page_size):
                raise urllib.error.URLError(f"partial tag page {page_number}: unexpected entry count")
            page_songs = [song for song in entries if is_song_entry(song.raw_title)]
            if not page_songs:
                raise urllib.error.URLError(f"no song entries on tag page {page_number}; source may be unavailable or its markup changed")
            page_urls = [song.url for song in page_songs]
            if len(set(page_urls)) != len(page_urls) or seen_urls.intersection(page_urls):
                raise urllib.error.URLError(
                    f"duplicate song entries on tag page {page_number}; pagination may have shifted or repeated"
                )
            seen_urls.update(page_urls)
            for song in page_songs:
                if song.raw_title not in seen:
                    seen.add(song.raw_title)
                    songs.append(song)
        return songs

    def fetch_html(self, url: str) -> str:
        return fetch_text(url, timeout=self.timeout, user_agent=USER_AGENT)


def validated_tag_page(page_html: str) -> tuple[list[RawSong], int, int]:
    soup = BeautifulSoup(page_html, "html.parser")
    containers = soup.select(".cmd_tag")
    if len(containers) != 1:
        raise urllib.error.URLError("no song entries: tag result container missing or ambiguous")
    container = containers[0]
    lists = container.select("ul.atwiki-page-list")
    if len(lists) != 1:
        raise urllib.error.URLError("no song entries: result list missing or ambiguous")
    songs = []
    for row in lists[0].find_all("li", recursive=False):
        links = row.find_all("a", href=True)
        if len(links) != 1:
            raise urllib.error.URLError("malformed tag entry")
        link = links[0]
        url = urllib.parse.urljoin(SITE_ROOT_URL, link["href"])
        parsed = urllib.parse.urlsplit(url)
        title = normalize_title(link.get_text())
        if parsed.scheme != "https" or parsed.netloc != "w.atwiki.jp" or parsed.query or parsed.fragment or not re.fullmatch(r"/hmiku/pages/\d+\.html", parsed.path) or not title:
            raise urllib.error.URLError("malformed tag entry")
        songs.append(RawSong(title, url))
    pagination = []
    for navigation in container.select(".atwiki-pagination-wrap"):
        current = [int(span.get_text(strip=True)[1:-1]) for span in navigation.find_all("span")
                   if re.fullmatch(r"\[\d+\]", span.get_text(strip=True))]
        if len(current) != 1 or current[0] < 1:
            raise urllib.error.URLError("invalid current tag page")
        numbers = current[:]
        for link in navigation.find_all("a", href=True):
            target = urllib.parse.urlsplit(link["href"])
            if target.netloc not in {"", "w.atwiki.jp"} or (target.path and not target.path.startswith("/hmiku/tag/")):
                raise urllib.error.URLError("invalid tag pagination target")
            value = urllib.parse.parse_qs(target.query).get("p", [])
            if len(value) != 1 or not value[0].isdigit() or int(value[0]) < 1:
                raise urllib.error.URLError("invalid tag pagination link")
            numbers.append(int(value[0]))
        pagination.append((current[0], max(numbers)))
    if len(set(pagination)) > 1:
        raise urllib.error.URLError("inconsistent tag pagination")
    current, last = pagination[0] if pagination else (1, 1)
    return songs, current, last


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
    return validated_tag_page(first_page_html)[2]


def extract_songs(page_html: str) -> list[RawSong]:
    return validated_tag_page(page_html)[0]


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
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise urllib.error.URLError(f"popularity tag fetch failed: {label}: {exc}") from exc
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
