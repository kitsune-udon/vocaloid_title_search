from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator, Mapping, Sequence

from vocaloid_title_search.database import rebuild_database, save_song_detail_entry
from vocaloid_title_search.models import PopularityInfo, RawSong


SOURCE_URL = "https://example.test/source"
MELT_URL = "https://w.atwiki.jp/hmiku/pages/82.html"


@contextmanager
def temporary_db(
    songs: Sequence[RawSong] | None = None,
    popularity: Mapping[str, PopularityInfo] | None = None,
    publication_years: Mapping[str, int] | None = None,
    source_url: str = SOURCE_URL,
) -> Iterator[Path]:
    with TemporaryDirectory() as directory:
        db_path = Path(directory) / "songs.sqlite3"
        if songs is not None:
            rebuild_database(db_path, songs, dict(popularity or {}), source_url)
            for song in songs:
                save_song_detail_entry(
                    db_path,
                    song.url,
                    {
                        "page_title": song.raw_title,
                        "source_url": song.url,
                        "published_year": dict(publication_years or {}).get(song.raw_title),
                    },
                )
        yield db_path


def raw_song(raw_title: str = "メルト", url: str = MELT_URL) -> RawSong:
    return RawSong(raw_title, url)


def popularity(score: int = 1000, label: str = "テンミリオン達成曲", order: int = 1) -> PopularityInfo:
    return PopularityInfo(score, label, order)


def store_composer_detail(
    db_path: Path,
    url: str = MELT_URL,
    names: Sequence[str] = ("ryo",),
    page_title: str = "メルト",
) -> None:
    save_song_detail_entry(
        db_path,
        url,
        {
            "page_title": page_title,
            "source_url": url,
            "credits": {"composer": list(names)},
        },
    )
