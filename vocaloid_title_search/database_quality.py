"""Quality checks for the local SQLite song database."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vocaloid_title_search.database import (
    DATABASE_SCHEMA_VERSION,
    DETAIL_SCHEMA_VERSION,
    REQUIRED_METADATA_KEYS,
    connect_readonly,
)


REQUIRED_TABLES = {"songs", "metadata", "song_details", "song_credit_people"}
REQUIRED_QUALITY_METADATA_KEYS = REQUIRED_METADATA_KEYS | {
    "detail_count",
    "detail_schema_version",
}


@dataclass(frozen=True)
class DatabaseQualityReport:
    """Result of a database quality check."""

    db_path: Path
    counts: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "db_path": str(self.db_path),
            "counts": self.counts,
            "metadata": self.metadata,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def validate_database_quality(db_path: Path) -> DatabaseQualityReport:
    """Validate DB readiness and report useful data quality counts."""

    errors: list[str] = []
    warnings: list[str] = []
    counts: dict[str, int] = {}
    metadata: dict[str, str] = {}

    if not db_path.exists():
        return DatabaseQualityReport(
            db_path=db_path,
            errors=[f"database file does not exist: {db_path}"],
        )

    try:
        with closing(connect_readonly(db_path)) as connection:
            table_names = load_table_names(connection)
            missing_tables = sorted(REQUIRED_TABLES - table_names)
            if missing_tables:
                return DatabaseQualityReport(
                    db_path=db_path,
                    errors=[f"missing required tables: {', '.join(missing_tables)}"],
                )

            metadata = dict(connection.execute("SELECT key, value FROM metadata"))
            counts.update(load_core_counts(connection))
            detail_json_counts = count_detail_json_values(connection)
            counts.update(detail_json_counts)
            errors.extend(validate_metadata(metadata, counts))
            errors.extend(validate_relations(connection))
            errors.extend(validate_detail_json_counts(detail_json_counts))
            warnings.extend(validate_coverage(counts))
    except sqlite3.DatabaseError as exc:
        errors.append(f"database read failed: {exc}")

    return DatabaseQualityReport(
        db_path=db_path,
        counts=counts,
        metadata=metadata,
        errors=errors,
        warnings=warnings,
    )


def load_table_names(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    return {row[0] for row in rows}


def load_core_counts(connection: sqlite3.Connection) -> dict[str, int]:
    return {
        "songs": scalar_count(connection, "SELECT COUNT(*) FROM songs"),
        "details": scalar_count(connection, "SELECT COUNT(*) FROM song_details"),
        "songs_with_composer": scalar_count(
            connection,
            """
            SELECT COUNT(DISTINCT song_url)
            FROM song_credit_people
            WHERE role = 'composer'
            """,
        ),
        "songs_with_published_year": scalar_count(
            connection,
            "SELECT COUNT(*) FROM song_details WHERE published_year IS NOT NULL",
        ),
        "detail_schema_mismatch": scalar_count(
            connection,
            "SELECT COUNT(*) FROM song_details WHERE schema_version <> ?",
            (DETAIL_SCHEMA_VERSION,),
        ),
    }


def scalar_count(
    connection: sqlite3.Connection,
    sql: str,
    parameters: tuple[object, ...] = (),
) -> int:
    return int(connection.execute(sql, parameters).fetchone()[0])


def count_detail_json_values(connection: sqlite3.Connection) -> dict[str, int]:
    counts = {
        "invalid_detail_json": 0,
        "videos": 0,
        "related_videos": 0,
        "videos_with_thumbnail": 0,
        "videos_with_title": 0,
    }
    rows = connection.execute("SELECT payload_json FROM song_details")
    for (payload_json,) in rows:
        try:
            detail = json.loads(payload_json)
        except json.JSONDecodeError:
            counts["invalid_detail_json"] += 1
            continue
        count_video_list(detail.get("videos"), counts, "videos")
        count_video_list(detail.get("related_videos"), counts, "related_videos")
    return counts


def count_video_list(value: object, counts: dict[str, int], key: str) -> None:
    if not isinstance(value, list):
        return
    counts[key] += len(value)
    for item in value:
        if not isinstance(item, dict):
            continue
        if item.get("thumbnail_url"):
            counts["videos_with_thumbnail"] += 1
        if item.get("title"):
            counts["videos_with_title"] += 1


def validate_metadata(metadata: dict[str, str], counts: dict[str, int]) -> list[str]:
    errors: list[str] = []
    missing_keys = sorted(REQUIRED_QUALITY_METADATA_KEYS - metadata.keys())
    if missing_keys:
        errors.append(f"missing metadata keys: {', '.join(missing_keys)}")
    if metadata.get("schema_version") != DATABASE_SCHEMA_VERSION:
        errors.append(
            f"metadata.schema_version must be {DATABASE_SCHEMA_VERSION}, got {metadata.get('schema_version')!r}"
        )
    if metadata.get("detail_schema_version") != DETAIL_SCHEMA_VERSION:
        errors.append(
            f"metadata.detail_schema_version must be {DETAIL_SCHEMA_VERSION}, got {metadata.get('detail_schema_version')!r}"
        )
    errors.extend(validate_metadata_count(metadata, "song_count", counts.get("songs", 0)))
    errors.extend(validate_metadata_count(metadata, "detail_count", counts.get("details", 0)))
    if counts.get("songs", 0) <= 0:
        errors.append("songs table is empty")
    if counts.get("details") != counts.get("songs"):
        errors.append(
            f"song_details count must match songs count: details={counts.get('details', 0)}, songs={counts.get('songs', 0)}"
        )
    if counts.get("detail_schema_mismatch", 0):
        errors.append(f"song_details has schema_version mismatch rows: {counts['detail_schema_mismatch']}")
    return errors


def validate_metadata_count(metadata: dict[str, str], key: str, actual: int) -> list[str]:
    if key not in metadata:
        return []
    try:
        expected = int(metadata[key])
    except ValueError:
        return [f"metadata.{key} must be an integer, got {metadata[key]!r}"]
    if expected != actual:
        return [f"metadata.{key} must match table count: metadata={expected}, actual={actual}"]
    return []


def validate_relations(connection: sqlite3.Connection) -> list[str]:
    errors: list[str] = []
    orphan_details = scalar_count(
        connection,
        """
        SELECT COUNT(*)
        FROM song_details
        LEFT JOIN songs ON songs.song_url = song_details.url
        WHERE songs.song_url IS NULL
        """,
    )
    orphan_credit_people = scalar_count(
        connection,
        """
        SELECT COUNT(*)
        FROM song_credit_people
        LEFT JOIN songs ON songs.song_url = song_credit_people.song_url
        WHERE songs.song_url IS NULL
        """,
    )
    if orphan_details:
        errors.append(f"song_details has orphan rows: {orphan_details}")
    if orphan_credit_people:
        errors.append(f"song_credit_people has orphan rows: {orphan_credit_people}")
    return errors


def validate_detail_json_counts(counts: dict[str, int]) -> list[str]:
    if counts.get("invalid_detail_json", 0):
        return [f"song_details has invalid JSON rows: {counts['invalid_detail_json']}"]
    return []


def validate_coverage(counts: dict[str, int]) -> list[str]:
    warnings: list[str] = []
    songs = counts.get("songs", 0)
    if not songs:
        return warnings
    if counts.get("songs_with_composer", 0) == 0:
        warnings.append("composer index is empty")
    if counts.get("songs_with_published_year", 0) == 0:
        warnings.append("published year coverage is empty")
    if counts.get("videos", 0) and counts.get("videos_with_thumbnail", 0) == 0:
        warnings.append("video thumbnails are empty")
    return warnings
