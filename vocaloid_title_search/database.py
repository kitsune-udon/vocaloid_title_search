"""SQLite persistence for Vocaloid song entries."""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unicodedata
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from vocaloid_title_search.models import (
    PopularityInfo,
    RawSong,
    SearchResult,
    SongEntry,
)
from vocaloid_title_search.wiki import POPULARITY_TAGS


DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "vocaloid_titles.sqlite3"
POPULARITY_ORDER = "popularity"
TITLE_LENGTH_ASC_ORDER = "title_length_asc"
TITLE_LENGTH_DESC_ORDER = "title_length_desc"
PUBLISHED_YEAR_ASC_ORDER = "published_year_asc"
PUBLISHED_YEAR_DESC_ORDER = "published_year_desc"
DATABASE_SCHEMA_VERSION = "7"
REQUIRED_METADATA_KEYS = {"schema_version", "fetched_at", "song_count", "title_length_rule"}
DETAIL_SCHEMA_VERSION = "1"


def ensure_database(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS songs (
            raw_title TEXT PRIMARY KEY,
            song_url TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL,
            artist TEXT NOT NULL DEFAULT '',
            artist_note TEXT NOT NULL DEFAULT '',
            title_length INTEGER NOT NULL,
            sort_order INTEGER NOT NULL,
            popularity_score INTEGER NOT NULL DEFAULT 0,
            popularity_label TEXT NOT NULL DEFAULT '',
            popularity_order INTEGER NOT NULL DEFAULT 0,
            source_url TEXT NOT NULL,
            fetched_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS song_details (
            url TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL,
            published_year INTEGER,
            fetched_at TEXT NOT NULL,
            source_fetched_at TEXT NOT NULL DEFAULT '',
            schema_version TEXT NOT NULL DEFAULT '1',
            FOREIGN KEY (url) REFERENCES songs(song_url) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS song_credit_people (
            song_url TEXT NOT NULL,
            role TEXT NOT NULL,
            name TEXT NOT NULL,
            normalized_name TEXT NOT NULL,
            PRIMARY KEY (song_url, role, normalized_name),
            FOREIGN KEY (song_url) REFERENCES songs(song_url) ON DELETE CASCADE
        );

        """
    )
    connection.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_songs_title_length
            ON songs(title_length, sort_order);

        CREATE INDEX IF NOT EXISTS idx_songs_popularity
            ON songs(title_length, popularity_score DESC, popularity_order, sort_order);

        CREATE UNIQUE INDEX IF NOT EXISTS idx_songs_url_unique
            ON songs(song_url);

        CREATE INDEX IF NOT EXISTS idx_songs_popularity_label
            ON songs(popularity_label, title_length, popularity_score DESC);

        CREATE INDEX IF NOT EXISTS idx_song_details_fetched_at
            ON song_details(fetched_at);

        CREATE INDEX IF NOT EXISTS idx_song_details_published_year
            ON song_details(published_year, url);

        CREATE INDEX IF NOT EXISTS idx_song_credit_people_role_name
            ON song_credit_people(role, normalized_name);

        CREATE INDEX IF NOT EXISTS idx_song_credit_people_name
            ON song_credit_people(normalized_name);
        """
    )


def rebuild_database(
    db_path: Path,
    raw_songs: list[RawSong],
    popularity_map: dict[str, PopularityInfo],
    source_url: str,
) -> None:
    """Build a new song database file and atomically replace the old one."""
    fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = temporary_database_path(db_path)
    try:
        with closing(sqlite3.connect(temp_path)) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            ensure_database(connection)
            connection.executemany(
                """
                INSERT INTO songs (
                    raw_title,
                    song_url,
                    title,
                    artist,
                    artist_note,
                    title_length,
                    sort_order,
                    popularity_score,
                    popularity_label,
                    popularity_order,
                    source_url,
                    fetched_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    song_row(
                        raw_song,
                        sort_order,
                        popularity_map,
                        source_url,
                        fetched_at,
                    )
                    for sort_order, raw_song in enumerate(raw_songs, start=1)
                ],
            )
            connection.executemany(
                "INSERT INTO metadata (key, value) VALUES (?, ?)",
                [
                    ("schema_version", DATABASE_SCHEMA_VERSION),
                    ("source_url", source_url),
                    ("fetched_at", fetched_at),
                    ("song_count", str(len(raw_songs))),
                    ("title_length_rule", "unicode_nfc_grapheme_cluster_whitespace_excluded"),
                    ("popularity_source_tags", ",".join(label for label, _ in POPULARITY_TAGS)),
                    ("publication_year_source", "song_detail_pages"),
                    ("detail_schema_version", DETAIL_SCHEMA_VERSION),
                    ("detail_count", "0"),
                ],
            )
            refresh_detail_metadata(connection)
            connection.commit()
        os.replace(temp_path, db_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def temporary_database_path(db_path: Path) -> Path:
    handle = tempfile.NamedTemporaryFile(
        prefix=f".{db_path.name}.",
        suffix=".tmp",
        dir=db_path.parent,
        delete=False,
    )
    handle.close()
    return Path(handle.name)


def song_row(
    raw_song: RawSong,
    sort_order: int,
    popularity_map: dict[str, PopularityInfo],
    source_url: str,
    fetched_at: str,
) -> tuple[str, str, str, str, str, int, int, int, str, int, str, str]:
    song = SongEntry.from_raw(raw_song.raw_title, raw_song.url)
    popularity = popularity_map.get(raw_song.raw_title, PopularityInfo())
    return (
        song.raw_title,
        song.url,
        song.title,
        song.artist,
        song.artist_note,
        song.title_length,
        sort_order,
        popularity.score,
        popularity.label,
        popularity.order,
        source_url,
        fetched_at,
    )


def load_titles_by_length(
    db_path: Path,
    n_chars: int | None,
    sort_order: str,
    popularity_labels: list[str] | None = None,
    composer_query: str = "",
    published_year: int | None = None,
) -> list[SearchResult]:
    return load_paged_titles(
        db_path,
        n_chars,
        sort_order,
        popularity_labels,
        composer_query,
        published_year,
        limit=None,
        offset=0,
    )[0]


def load_paged_titles(
    db_path: Path,
    n_chars: int | None,
    sort_order: str,
    popularity_labels: list[str] | None = None,
    composer_query: str = "",
    published_year: int | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> tuple[list[SearchResult], int]:
    with closing(connect_readonly(db_path)) as connection:
        where_clauses, parameters = title_search_filters(
            n_chars,
            popularity_labels,
            composer_query,
            published_year,
        )
        total = connection.execute(
            f"""
            SELECT COUNT(*)
            FROM songs
            JOIN song_details ON song_details.url = songs.song_url
            {sql_where_clause(where_clauses)}
            """,
            parameters,
        ).fetchone()[0]
        limit_clause = ""
        query_parameters = list(parameters)
        if limit is not None:
            limit_clause = "LIMIT ? OFFSET ?"
            query_parameters.extend([limit, max(0, offset)])
        rows = connection.execute(
            f"""
            SELECT
                songs.title,
                songs.title_length,
                COALESCE(composers.composer_names, ''),
                songs.artist_note,
                songs.song_url,
                songs.popularity_score,
                songs.popularity_label,
                song_details.published_year
            FROM songs
            JOIN song_details ON song_details.url = songs.song_url
            LEFT JOIN (
                SELECT song_url, GROUP_CONCAT(name, ' / ') AS composer_names
                FROM (
                    SELECT song_url, name
                    FROM song_credit_people
                    WHERE role = 'composer'
                    ORDER BY name
                )
                GROUP BY song_url
            ) composers ON composers.song_url = songs.song_url
            {sql_where_clause(where_clauses)}
            ORDER BY {sql_order_by(sort_order)}
            {limit_clause}
            """,
            query_parameters,
        )
        results = [
            SearchResult(
                title=row[0],
                title_length=row[1],
                artist=row[2],
                artist_note=row[3],
                url=row[4],
                popularity_score=row[5],
                popularity_label=row[6],
                published_year=row[7],
            )
            for row in rows
        ]
        return results, total


def title_search_filters(
    n_chars: int | None,
    popularity_labels: list[str] | None = None,
    composer_query: str = "",
    published_year: int | None = None,
) -> tuple[list[str], list[object]]:
    where_clauses: list[str] = []
    parameters: list[object] = []
    if n_chars is not None:
        where_clauses.append("songs.title_length = ?")
        parameters.append(n_chars)
    if popularity_labels:
        placeholders = ", ".join("?" for _ in popularity_labels)
        where_clauses.append(f"songs.popularity_label IN ({placeholders})")
        parameters.extend(popularity_labels)
    if published_year is not None:
        where_clauses.append("song_details.published_year = ?")
        parameters.append(published_year)
    normalized_composer = normalize_credit_name(composer_query)
    if normalized_composer:
        where_clauses.append(
            """
            EXISTS (
                SELECT 1
                FROM song_credit_people person
                WHERE person.song_url = songs.song_url
                  AND person.role = 'composer'
                  AND person.normalized_name LIKE ? ESCAPE '\\'
            )
            """
        )
        parameters.append(f"%{escape_like_pattern(normalized_composer)}%")
    return where_clauses, parameters


def sql_where_clause(where_clauses: list[str]) -> str:
    if not where_clauses:
        return ""
    return f"WHERE {' AND '.join(where_clauses)}"


def load_popularity_labels(db_path: Path) -> list[str]:
    with closing(connect_readonly(db_path)) as connection:
        rows = connection.execute(
            """
            SELECT popularity_label
            FROM songs
            WHERE popularity_label <> ''
            GROUP BY popularity_label
            ORDER BY MAX(popularity_score) DESC, popularity_label
            """
        )
        return [row[0] for row in rows]


def load_metadata(db_path: Path) -> dict[str, str]:
    with closing(connect_readonly(db_path)) as connection:
        rows = connection.execute("SELECT key, value FROM metadata")
        return dict(rows)


def load_statistics(db_path: Path) -> dict[str, object]:
    with closing(connect_readonly(db_path)) as connection:
        total_songs = connection.execute("SELECT COUNT(*) FROM songs").fetchone()[0]
        detail_count = connection.execute("SELECT COUNT(*) FROM song_details").fetchone()[0]
        with_composer = connection.execute(
            """
            SELECT COUNT(DISTINCT song_url)
            FROM song_credit_people
            WHERE role = 'composer'
            """
        ).fetchone()[0]
        with_published_year = connection.execute(
            "SELECT COUNT(*) FROM song_details WHERE published_year IS NOT NULL"
        ).fetchone()[0]
        return {
            "total_songs": total_songs,
            "detail_count": detail_count,
            "with_composer": with_composer,
            "with_published_year": with_published_year,
            "by_title_length": [
                {"length": row[0], "count": row[1]}
                for row in connection.execute(
                    """
                    SELECT title_length, COUNT(*)
                    FROM songs
                    GROUP BY title_length
                    ORDER BY title_length
                    """
                )
            ],
            "by_published_year": [
                {"year": row[0], "count": row[1]}
                for row in connection.execute(
                    """
                    SELECT published_year, COUNT(*)
                    FROM song_details
                    WHERE published_year IS NOT NULL
                    GROUP BY published_year
                    ORDER BY published_year
                    """
                )
            ],
            "by_popularity_label": [
                {"label": row[0], "count": row[1]}
                for row in connection.execute(
                    """
                    SELECT popularity_label, COUNT(*)
                    FROM songs
                    WHERE popularity_label <> ''
                    GROUP BY popularity_label
                    ORDER BY MAX(popularity_score) DESC, popularity_label
                    """
                )
            ],
            "top_composers": [
                {"name": row[0], "count": row[1]}
                for row in connection.execute(
                    """
                    SELECT MIN(name), COUNT(DISTINCT song_url) AS song_count
                    FROM song_credit_people
                    WHERE role = 'composer'
                    GROUP BY normalized_name
                    ORDER BY song_count DESC, MIN(name)
                    LIMIT 30
                    """
                )
            ],
        }


def database_is_ready(db_path: Path) -> bool:
    if not db_path.exists():
        return False
    try:
        with closing(connect_readonly(db_path)) as connection:
            keys = {
                row[0]
                for row in connection.execute("SELECT key FROM metadata").fetchall()
            }
            schema_version = dict(connection.execute("SELECT key, value FROM metadata")).get("schema_version")
            song_count = connection.execute("SELECT COUNT(*) FROM songs").fetchone()[0]
            detail_count = connection.execute("SELECT COUNT(*) FROM song_details").fetchone()[0]
    except sqlite3.DatabaseError:
        return False
    return (
        REQUIRED_METADATA_KEYS.issubset(keys)
        and schema_version == DATABASE_SCHEMA_VERSION
        and song_count > 0
        and detail_count == song_count
    )


def connect_readonly(db_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def load_song_detail(db_path: Path, url: str) -> dict[str, object] | None:
    with closing(connect_readonly(db_path)) as connection:
        row = connection.execute(
            "SELECT payload_json FROM song_details WHERE url = ?",
            (url,),
        ).fetchone()
    return json.loads(row[0]) if row else None


def load_song_detail_payloads(db_path: Path) -> list[tuple[str, dict[str, object]]]:
    with closing(connect_readonly(db_path)) as connection:
        rows = connection.execute(
            "SELECT url, payload_json FROM song_details ORDER BY url"
        ).fetchall()
    return [(url, json.loads(payload_json)) for url, payload_json in rows]


def list_song_urls(
    db_path: Path,
    limit: int | None = None,
    title_length: int | None = None,
) -> list[str]:
    where_clauses = ["song_url <> ''"]
    parameters: list[object] = []
    if title_length is not None:
        where_clauses.append("title_length = ?")
        parameters.append(title_length)
    sql = f"""
        SELECT song_url
        FROM songs
        WHERE {' AND '.join(where_clauses)}
        ORDER BY popularity_score DESC, popularity_order, sort_order
    """
    if limit is not None:
        sql += " LIMIT ?"
        parameters.append(limit)
    with closing(connect_readonly(db_path)) as connection:
        rows = connection.execute(sql, parameters).fetchall()
    return [row[0] for row in rows]


def save_song_detail_entry(db_path: Path, url: str, detail: dict[str, object]) -> None:
    fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        ensure_database(connection)
        save_song_detail(connection, url, detail, fetched_at)
        refresh_detail_metadata(connection)
        connection.commit()


def save_song_detail(
    connection: sqlite3.Connection,
    url: str,
    detail: dict[str, object],
    fetched_at: str,
) -> None:
    connection.execute(
        """
        INSERT OR REPLACE INTO song_details (
            url,
            payload_json,
            published_year,
            fetched_at,
            source_fetched_at,
            schema_version
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            url,
            json.dumps(detail, ensure_ascii=False, separators=(",", ":")),
            detail_published_year(detail),
            fetched_at,
            "",
            DETAIL_SCHEMA_VERSION,
        ),
    )
    save_credit_people(connection, url, detail)


def save_credit_people(
    connection: sqlite3.Connection,
    song_url: str,
    detail: dict[str, object],
) -> None:
    connection.execute("DELETE FROM song_credit_people WHERE song_url = ?", (song_url,))
    rows = credit_people_rows(song_url, detail)
    connection.executemany(
        """
        INSERT OR IGNORE INTO song_credit_people (
            song_url,
            role,
            name,
            normalized_name
        )
        VALUES (?, ?, ?, ?)
        """,
        rows,
    )


def detail_published_year(detail: dict[str, object]) -> int | None:
    year = detail.get("published_year")
    return year if isinstance(year, int) else None


def credit_people_rows(song_url: str, detail: dict[str, object]) -> list[tuple[str, str, str, str]]:
    credits = detail.get("credits")
    if not isinstance(credits, dict):
        return []
    rows: list[tuple[str, str, str, str]] = []
    for role in ("composer",):
        values = credits.get(role)
        if not isinstance(values, list):
            continue
        for value in values:
            if not isinstance(value, str):
                continue
            name = value.strip()
            normalized_name = normalize_credit_name(name)
            if name and normalized_name:
                rows.append((song_url, role, name, normalized_name))
    return rows


def normalize_credit_name(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold().strip()


def escape_like_pattern(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def refresh_detail_metadata(connection: sqlite3.Connection) -> None:
    detail_count = connection.execute("SELECT COUNT(*) FROM song_details").fetchone()[0]
    connection.executemany(
        "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
        [
            ("detail_count", str(detail_count)),
        ],
    )


def sql_order_by(sort_order: str) -> str:
    if sort_order == POPULARITY_ORDER:
        return "popularity_score DESC, popularity_order, sort_order"
    if sort_order == TITLE_LENGTH_ASC_ORDER:
        return "title_length ASC, popularity_score DESC, popularity_order, sort_order"
    if sort_order == TITLE_LENGTH_DESC_ORDER:
        return "title_length DESC, popularity_score DESC, popularity_order, sort_order"
    if sort_order == PUBLISHED_YEAR_ASC_ORDER:
        return "song_details.published_year IS NULL, song_details.published_year ASC, popularity_score DESC, popularity_order, sort_order"
    if sort_order == PUBLISHED_YEAR_DESC_ORDER:
        return "song_details.published_year IS NULL, song_details.published_year DESC, popularity_score DESC, popularity_order, sort_order"
    raise ValueError(f"unsupported sort order: {sort_order}")
