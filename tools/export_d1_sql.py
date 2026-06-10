#!/usr/bin/env python3
"""Export the local SQLite database as SQL suitable for Cloudflare D1."""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from contextlib import closing
from pathlib import Path


TABLES = ["songs", "metadata", "song_details", "song_credit_people"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, default=Path("vocaloid_titles.sqlite3"))
    parser.add_argument("--output", type=Path, default=Path("release/d1/vocaloid_titles.sql"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.db_path.exists():
        print(f"DB not found: {args.db_path}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(f"file:{args.db_path}?mode=ro", uri=True)) as connection:
        validate_database(connection)
        with args.output.open("w", encoding="utf-8", newline="\n") as output:
            write_export(connection, output)
    print(f"Exported D1 SQL: {args.output}")
    return 0


def validate_database(connection: sqlite3.Connection) -> None:
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        raise SystemExit(f"SQLite integrity_check failed: {integrity}")
    metadata = dict(connection.execute("SELECT key, value FROM metadata"))
    required = {"schema_version", "fetched_at", "song_count", "title_length_rule"}
    missing = sorted(required - metadata.keys())
    if missing:
        raise SystemExit(f"DB metadata missing: {', '.join(missing)}")


def write_export(connection: sqlite3.Connection, output) -> None:
    for table in reversed(TABLES):
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
        ORDER BY name
        """
    ):
        output.write(f"{sql};\n")


def write_rows(connection: sqlite3.Connection, output, table: str) -> None:
    columns = [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]
    column_sql = ", ".join(quote_identifier(column) for column in columns)
    for row in connection.execute(f"SELECT {column_sql} FROM {quote_identifier(table)}"):
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
