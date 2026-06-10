"""Domain models and normalization rules for Vocaloid song entries."""

from __future__ import annotations

from dataclasses import dataclass
import unicodedata

import regex


NON_SONG_TITLES = {"曲一覧"}
IGNORED_BLANK_CHARS = {
    "\u200b",  # zero width space
    "\u200c",  # zero width non-joiner
    "\u2060",  # word joiner
    "\ufeff",  # zero width no-break space
    "\u2800",  # braille pattern blank
}


@dataclass(frozen=True)
class PopularityInfo:
    score: int = 0
    label: str = ""
    order: int = 0


@dataclass(frozen=True)
class RawSong:
    raw_title: str
    url: str


@dataclass(frozen=True)
class SongEntry:
    raw_title: str
    url: str
    title: str
    artist: str
    artist_note: str
    title_length: int

    @classmethod
    def from_raw(cls, raw_title: str, url: str = "") -> "SongEntry":
        title, artist, artist_note = split_title_artist(raw_title)
        return cls(
            raw_title=raw_title,
            url=url,
            title=title,
            artist=artist,
            artist_note=artist_note,
            title_length=count_title_chars(title),
        )

    @property
    def is_song(self) -> bool:
        return self.title not in NON_SONG_TITLES


@dataclass(frozen=True)
class SearchResult:
    title: str
    title_length: int
    artist: str
    artist_note: str
    url: str
    popularity_score: int
    popularity_label: str
    published_year: int | None = None


def split_title_artist(raw_entry: str) -> tuple[str, str, str]:
    raw_entry = normalize_title_text(raw_entry)
    title, separator, rest = raw_entry.partition("/")
    if not separator:
        return raw_entry, "", ""

    artist, _, artist_note = rest.partition("/")
    return title.strip(), artist.strip(), artist_note.strip()


def count_title_chars(title: str) -> int:
    normalized_title = normalize_title_text(title)
    return sum(
        1
        for cluster in grapheme_clusters(normalized_title)
        if is_counted_cluster(cluster)
    )


def grapheme_clusters(value: str) -> list[str]:
    return regex.findall(r"\X", value)


def is_counted_cluster(cluster: str) -> bool:
    if cluster.isspace():
        return False
    if all(char in IGNORED_BLANK_CHARS for char in cluster):
        return False
    return True


def normalize_title_text(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def is_song_entry(raw_entry: str) -> bool:
    return SongEntry.from_raw(raw_entry).is_song
