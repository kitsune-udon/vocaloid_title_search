#!/usr/bin/env python3
"""Export the local SQLite database as SQL suitable for Cloudflare D1."""

from __future__ import annotations

import argparse
import json
import uuid
import os
import tempfile
import re
import sqlite3
import sys
from contextlib import closing
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vocaloid_title_search.database import connect_readonly, statistics_from_connection
from vocaloid_title_search.database_quality import (load_core_counts, validate_metadata, validate_relations,
                                                  count_detail_json_values, validate_detail_json_counts,
                                                  count_song_value_errors, validate_song_values)

PUBLICATION_KEY = "api_publication_v1"

TABLES = ["songs", "metadata", "song_details", "song_credit_people"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, default=Path("vocaloid_titles.sqlite3"))
    parser.add_argument("--from-sql", type=Path, help="Convert a remote D1 export into validated replacement SQL.")
    parser.add_argument("--output", type=Path, default=Path("release/d1/vocaloid_titles.sql"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.from_sql:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(":memory:")) as connection:
            connection.executescript(args.from_sql.read_text(encoding="utf-8"))
            existing_tables = {row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )}
            empty_database = not existing_tables.intersection(TABLES)
            if not empty_database:
                validate_database(connection)
            export_atomic(connection, args.output, empty_database=empty_database)
        print(f"Prepared rollback SQL: {args.output}")
        return 0
    if not args.db_path.exists():
        print(f"DB not found: {args.db_path}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with closing(connect_readonly(args.db_path)) as connection:
        connection.execute("BEGIN")
        validate_database(connection)
        export_atomic(connection, args.output, publish=True)
    print(f"Exported D1 SQL: {args.output}")
    return 0


def export_atomic(connection: sqlite3.Connection, output_path: Path, *, empty_database: bool = False, publish: bool = False) -> None:
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=output_path.parent, prefix=f".{output_path.name}.",
                                         delete=False) as output:
            temporary_path = Path(output.name)
            if empty_database:
                for table in ["metadata", "song_credit_people", "song_details", "songs"]:
                    output.write(f"DROP TABLE IF EXISTS {table};\n")
            else:
                write_export(connection, output, publish=publish)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_path, output_path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def validate_database(connection: sqlite3.Connection) -> None:
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        raise SystemExit(f"SQLite integrity_check failed: {integrity}")
    metadata = dict(connection.execute("SELECT key, value FROM metadata"))
    required = {"schema_version", "fetched_at", "song_count", "title_length_rule"}
    missing = sorted(required - metadata.keys())
    if missing:
        raise SystemExit(f"DB metadata missing: {', '.join(missing)}")


def publication_record(connection: sqlite3.Connection) -> str:
    """Validate the immutable source, then compute runtime data once per release."""
    metadata = dict(connection.execute("SELECT key, value FROM metadata"))
    metadata.pop(PUBLICATION_KEY, None)
    errors = validate_metadata(metadata, load_core_counts(connection)) + validate_relations(connection)
    errors += validate_song_values(count_song_value_errors(connection))
    errors += validate_detail_json_counts(count_detail_json_values(connection, {"niconico": set(), "youtube": set()}, require_complete=True))
    if errors:
        raise ValueError("Cannot publish: " + "; ".join(errors))
    return json.dumps({"version": 1, "revision": uuid.uuid4().hex, "metadata": metadata,
                       "statistics": statistics_from_connection(connection)}, ensure_ascii=False, separators=(",", ":"))


def write_export(connection: sqlite3.Connection, output, *, publish: bool = False) -> None:
    # Generate from the validated release snapshot, never trust a stale saved record.
    record = publication_record(connection) if publish else dict(connection.execute(
        "SELECT key, value FROM metadata")).get(PUBLICATION_KEY)
    for table in ["metadata", "song_credit_people", "song_details", "songs"]:
        output.write(f"DROP TABLE IF EXISTS {table};\n")
    for table in TABLES:
        sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        if sql is None:
            raise SystemExit(f"Table not found: {table}")
        output.write(f"{d1_create_table_sql(sql[0])};\n")
    for table in TABLES:
        write_rows(connection, output, table)
    for (sql,) in connection.execute(
        """
        SELECT sql
        FROM sqlite_master
        WHERE type = 'index' AND sql IS NOT NULL
          AND tbl_name IN ('songs', 'metadata', 'song_details', 'song_credit_people')
        ORDER BY name
        """
    ):
        output.write(f"{sql};\n")
    if publish:
        output.write("CREATE INDEX IF NOT EXISTS idx_songs_order ON songs (popularity_score DESC, popularity_order, sort_order);\n")
    # Readiness stays absent until every table, row and index has succeeded.
    # Rollback retains its original revision but restores it last as well.
    if record is not None:
        output.write("INSERT INTO metadata (key, value) VALUES (" + sql_literal(connection, PUBLICATION_KEY)
                     + ", " + sql_literal(connection, record) + ");\n")


def write_rows(connection: sqlite3.Connection, output, table: str) -> None:
    columns = [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]
    column_sql = ", ".join(quote_identifier(column) for column in columns)
    for row in connection.execute(f"SELECT {column_sql} FROM {quote_identifier(table)}"):
        if table == "metadata" and row[columns.index("key")] == PUBLICATION_KEY:
            continue
        values = ", ".join(sql_literal(connection, value) for value in row)
        output.write(f"INSERT INTO {quote_identifier(table)} ({column_sql}) VALUES ({values});\n")


def sql_literal(connection: sqlite3.Connection, value: object) -> str:
    return connection.execute("SELECT quote(?)", (value,)).fetchone()[0]


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def d1_create_table_sql(sql: str) -> str:
    """Cloudflare D1 is stricter about this DB's cross-column FKs.

    The production API is read-only and the source SQLite DB is validated before
    export, so D1 keeps the data and indexes but omits foreign key constraints.
    """
    lines = [line for line in sql.splitlines() if "FOREIGN KEY" not in line]
    return re.sub(r",\s*\)$", "\n)", "\n".join(lines), flags=re.MULTILINE)


if __name__ == "__main__":
    raise SystemExit(main())
