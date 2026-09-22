#!/usr/bin/env python3
"""Prepare immutable release inputs and rehearse restoration without contacting D1."""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timezone
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.export_d1_sql import TABLES, export_atomic
from vocaloid_title_search.database import connect_readonly
from vocaloid_title_search.database_quality import validate_database_quality
from vocaloid_title_search.quality_policy import QualityPolicy


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save_manifest(directory: Path, manifest: dict) -> None:
    temporary = directory / ".manifest.json.tmp"
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(directory / "manifest.json")


def prepare(source: Path, directory: Path, environment: str, database: str) -> None:
    snapshot = directory / "new-vocaloid_titles.sqlite3"
    with closing(connect_readonly(source)) as origin, closing(sqlite3.connect(snapshot)) as target:
        origin.backup(target)
    report = validate_database_quality(snapshot, require_video_metadata=True)
    (directory / "quality.json").write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    if not report.ok:
        raise ValueError("; ".join(report.errors))
    sql = directory / "new-vocaloid_titles.sql"
    with closing(connect_readonly(snapshot)) as connection:
        export_atomic(connection, sql)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    paths = subprocess.check_output(["git", "ls-files", "-cz", "--others", "--exclude-standard"], cwd=ROOT).split(b"\0")
    source_hash = hashlib.sha256()
    for name in sorted(set(paths) - {b""}):
        path = ROOT / name.decode()
        source_hash.update(name + b"\0")
        source_hash.update(path.read_bytes() if path.is_file() else b"<deleted>")
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(), "environment": environment,
        "database": database, "revision": revision, "source_tree_sha256": source_hash.hexdigest(),
        "dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT)),
        "policy": asdict(QualityPolicy()), "status": "prepared",
        "artifacts": {path.name: digest(path) for path in (snapshot, sql, directory / "quality.json")},
    }
    save_manifest(directory, manifest)


def table_state(connection: sqlite3.Connection) -> dict:
    names = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    return {name: {
        "columns": connection.execute(f"PRAGMA table_info({name})").fetchall(),
        "rows": sorted(connection.execute(f"SELECT * FROM {name}").fetchall(), key=repr),
        "indexes": sorted(connection.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name=? AND sql IS NOT NULL", (name,)).fetchall()),
    } for name in TABLES if name in names}


def rehearse(directory: Path) -> None:
    """Load new data, restore old SQL, and compare every application row and index."""
    with closing(sqlite3.connect(":memory:")) as expected, closing(sqlite3.connect(":memory:")) as restored:
        expected.executescript((directory / "remote-before.sql").read_text())
        restored.executescript((directory / "new-vocaloid_titles.sql").read_text())
        restored.executescript((directory / "rollback.sql").read_text())
        if table_state(expected) != table_state(restored):
            raise ValueError("rollback rehearsal did not restore application tables exactly")
        if table_state(expected):
            previous = directory / "previous.sqlite3"
            with closing(sqlite3.connect(previous)) as target:
                expected.backup(target)
            report = validate_database_quality(directory / "new-vocaloid_titles.sqlite3", require_video_metadata=True, baseline_path=previous)
            (directory / "quality-comparison.json").write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
            if not report.ok:
                raise ValueError("; ".join(report.errors))
    manifest = json.loads((directory / "manifest.json").read_text())
    manifest["rollback_verified"] = True
    for name in ("remote-before.sql", "rollback.sql", "previous.sqlite3", "quality-comparison.json"):
        if (directory / name).exists():
            manifest["artifacts"][name] = digest(directory / name)
    save_manifest(directory, manifest)


def verify(directory: Path) -> None:
    manifest = json.loads((directory / "manifest.json").read_text())
    if not manifest.get("rollback_verified"):
        raise ValueError("rollback rehearsal is required")
    for name, expected in manifest["artifacts"].items():
        if digest(directory / name) != expected:
            raise ValueError(f"release artifact changed after validation: {name}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "rehearse", "verify", "status"))
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--db-path", type=Path)
    parser.add_argument("--environment")
    parser.add_argument("--database")
    parser.add_argument("--status")
    args = parser.parse_args()
    if args.action == "prepare":
        prepare(args.db_path, args.directory, args.environment, args.database)
    elif args.action == "rehearse":
        rehearse(args.directory)
    elif args.action == "verify":
        verify(args.directory)
    else:
        path = args.directory / "manifest.json"
        if path.exists():
            manifest = json.loads(path.read_text())
            manifest["status"] = args.status
            manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
            save_manifest(args.directory, manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
