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
    credit_people_rows,
    detail_published_year,
)


from vocaloid_title_search.models import SongEntry
from vocaloid_title_search.wiki import POPULARITY_TAGS
from vocaloid_title_search.detail_contract import valid_detail
from vocaloid_title_search.video_metadata import video_ids_fingerprint
from vocaloid_title_search.quality_policy import QualityPolicy, compare_counts, video_refresh_errors


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
    comparison: dict[str, object] = field(default_factory=dict)

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
            "comparison": self.comparison,
        }


def validate_database_quality(db_path: Path, *, require_video_metadata: bool = False,
                              baseline_path: Path | None = None, policy: QualityPolicy = QualityPolicy()) -> DatabaseQualityReport:
    """Validate DB readiness and report useful data quality counts."""

    errors: list[str] = []
    warnings: list[str] = []
    counts: dict[str, int] = {}
    metadata: dict[str, str] = {}
    comparison: dict[str, object] = {}
    baseline = validate_database_quality(baseline_path) if baseline_path is not None else None
    if baseline is not None and not baseline.ok:
        errors.append("baseline database failed quality checks: " + "; ".join(baseline.errors))

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
            counts.update(count_song_value_errors(connection))
            errors.extend(validate_song_values(counts))
            video_ids = {"niconico": set(), "youtube": set()}
            detail_json_counts = count_detail_json_values(connection, video_ids, require_complete=require_video_metadata)
            counts.update(detail_json_counts)
            errors.extend(validate_metadata(metadata, counts))
            errors.extend(validate_relations(connection))
            errors.extend(validate_detail_json_counts(detail_json_counts))
            warnings.extend(validate_coverage(counts))
            if require_video_metadata:
                for service in ("niconico", "youtube"):
                    prefix = f"video_metadata_{service}_"
                    total = counts[f"{service}_unique_videos"]
                    if not total:
                        continue
                    if (
                        not metadata.get(prefix + "fetched_at")
                        or metadata.get(prefix + "total") != str(total)
                        or metadata.get(prefix + "ids_sha256") != video_ids_fingerprint(video_ids[service])
                    ):
                        errors.append(f"{service} metadata refresh is missing or stale; run refresh_video_metadata")
                    errors.extend(video_refresh_errors(metadata, service, total, policy,
                                                       baseline.metadata if baseline else None))
            if baseline is not None and baseline.ok:
                comparison, regressions = compare_counts(counts, baseline.counts, policy)
                errors.extend(regressions)
    except sqlite3.DatabaseError as exc:
        errors.append(f"database read failed: {exc}")

    return DatabaseQualityReport(
        db_path=db_path,
        counts=counts,
        metadata=metadata,
        errors=errors,
        warnings=warnings,
        comparison=comparison,
    )


def load_table_names(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    return {row[0] for row in rows}


def count_song_value_errors(connection: sqlite3.Connection) -> dict[str, int]:
    """Recompute searchable values from their source, not from stored aggregates."""
    invalid = 0
    positions = []
    scores = dict(POPULARITY_TAGS)
    scores[""] = 0
    for raw, title, artist, note, length, position, score, label, order in connection.execute(
        "SELECT raw_title, title, artist, artist_note, title_length, sort_order, "
        "popularity_score, popularity_label, popularity_order FROM songs"
    ):
        positions.append(position)
        if not isinstance(raw, str):
            invalid += 1
            continue
        expected = SongEntry.from_raw(raw)
        if (not expected.is_song or not expected.title.strip()
                or (title, artist, note, length) != (expected.title, expected.artist, expected.artist_note, expected.title_length)
                or type(length) is not int or type(position) is not int or position < 1
                or type(score) is not int or scores.get(label) != score
                or type(order) is not int or order < 0):
            invalid += 1
    return {"invalid_song_values": invalid,
            "invalid_song_order": int(set(positions) != set(range(1, len(positions) + 1)))}


def validate_song_values(counts: dict[str, int]) -> list[str]:
    errors = []
    if counts.get("invalid_song_values"):
        errors.append(f"songs has invalid song values rows: {counts['invalid_song_values']}")
    if counts.get("invalid_song_order"):
        errors.append("songs sort_order must be unique and contiguous from 1")
    return errors


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


def count_detail_json_values(
    connection: sqlite3.Connection, video_ids: dict[str, set[str]] | None = None, *, require_complete: bool = False,
) -> dict[str, int]:
    counts = {
        "invalid_detail_json": 0,
        "invalid_detail_contract": 0,
        "detail_index_mismatch": 0,
        "videos": 0,
        "related_videos": 0,
        "videos_with_thumbnail": 0,
        "videos_with_title": 0,
    }
    unique_ids = video_ids if video_ids is not None else {"niconico": set(), "youtube": set()}
    indexed_credits: dict[str, set[tuple]] = {}
    for row in connection.execute("SELECT song_url, role, name, normalized_name FROM song_credit_people"):
        indexed_credits.setdefault(row[0], set()).add(row)
    rows = connection.execute("SELECT url, payload_json, published_year FROM song_details")
    for url, payload_json, published_year in rows:
        try:
            detail = json.loads(payload_json)
        except json.JSONDecodeError:
            counts["invalid_detail_json"] += 1
            continue
        if not isinstance(detail, dict):
            counts["invalid_detail_json"] += 1
            continue
        if not valid_detail(detail, url, complete=require_complete):
            counts["invalid_detail_contract"] += 1
        # Match INSERT OR IGNORE: the first spelling for a normalized name wins.
        expected_credits = {}
        for row in credit_people_rows(url, detail):
            expected_credits.setdefault((row[0], row[1], row[3]), row)
        if (set(expected_credits.values()) != indexed_credits.get(url, set())
                or detail_published_year(detail) != published_year):
            counts["detail_index_mismatch"] += 1
        for section_name in ("videos", "related_videos"):
            section = detail.get(section_name)
            if isinstance(section, dict):
                for service in unique_ids:
                    entries = section.get(service, [])
                    if isinstance(entries, list):
                        unique_ids[service].update(
                            item["id"] for item in entries
                            if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"]
                        )
        count_video_list(detail.get("videos"), counts, "videos")
        count_video_list(detail.get("related_videos"), counts, "related_videos")
    counts.update({f"{service}_unique_videos": len(ids) for service, ids in unique_ids.items()})
    return counts


def count_video_list(value: object, counts: dict[str, int], key: str) -> None:
    if isinstance(value, dict):
        for service in ("niconico", "youtube"):
            count_video_list(value.get(service), counts, key)
        return
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
    errors = []
    for key, label in (("invalid_detail_json", "invalid JSON"),
                       ("invalid_detail_contract", "invalid detail contract"),
                       ("detail_index_mismatch", "detail/search index mismatch")):
        if counts.get(key, 0):
            errors.append(f"song_details has {label} rows: {counts[key]}")
    return errors


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
