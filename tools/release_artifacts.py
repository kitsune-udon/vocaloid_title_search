#!/usr/bin/env python3
"""Prepare immutable release inputs and rehearse restoration without contacting D1."""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timezone
from dataclasses import asdict
import hashlib
import json
import re
from pathlib import Path
import sqlite3
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.export_d1_sql import PUBLICATION_KEY, export_atomic, publication_record
from tools.release_state import digest, save_manifest, table_state, verify_artifacts
from vocaloid_title_search.database import connect_readonly
from vocaloid_title_search.database_quality import validate_database_quality
from vocaloid_title_search.quality_policy import QualityPolicy


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
        export_atomic(connection, sql, publish=True)
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


def rehearse(directory: Path) -> None:
    """Check forward publication against its snapshot, then restore every old row/index."""
    manifest = json.loads((directory / "manifest.json").read_text())
    verify_artifacts(directory, manifest)
    with closing(sqlite3.connect(":memory:")) as expected, closing(sqlite3.connect(":memory:")) as restored:
        expected.executescript((directory / "remote-before.sql").read_text())
        if manifest.get("mode") == "incremental-video-metadata":
            restored.executescript((directory / "remote-before.sql").read_text())
        restored.executescript((directory / "new-vocaloid_titles.sql").read_text())
        verify_forward(restored, directory / "new-vocaloid_titles.sqlite3")
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
    manifest["forward_verified"] = True
    manifest["rollback_verified"] = True
    for name in ("remote-before.sql", "rollback.sql", "previous.sqlite3", "quality-comparison.json"):
        if (directory / name).exists():
            manifest["artifacts"][name] = digest(directory / name)
    save_manifest(directory, manifest)


def verify(directory: Path) -> None:
    manifest = json.loads((directory / "manifest.json").read_text())
    if not manifest.get("rollback_verified"):
        raise ValueError("rollback rehearsal is required")
    if not manifest.get("forward_verified"):
        raise ValueError("forward rehearsal is required")
    verify_artifacts(directory, manifest)


def verify_forward(published: sqlite3.Connection, snapshot: Path) -> None:
    with closing(connect_readonly(snapshot)) as source:
        expected = table_state(source)
        actual = table_state(published)
        row = published.execute("SELECT value FROM metadata WHERE key=?", (PUBLICATION_KEY,)).fetchone()
        if row is None:
            raise ValueError("forward rehearsal has no publication record")
        record = json.loads(row[0])
        generated = json.loads(publication_record(source))
        if not re.fullmatch(r"[a-f0-9]{32}", str(record.pop("revision", ""))):
            raise ValueError("forward publication has invalid revision")
        generated.pop("revision", None)
        if record != generated:
            raise ValueError("forward publication does not match release snapshot")
        for state in (expected, actual):
            state["metadata"]["rows"] = [row for row in state["metadata"]["rows"] if row[0] != PUBLICATION_KEY]
        # Older local snapshots may lack the runtime-only ordering index.
        expected["songs"]["indexes"] = [row for row in expected["songs"]["indexes"] if row[0] != "idx_songs_order"]
        actual["songs"]["indexes"] = [row for row in actual["songs"]["indexes"] if row[0] != "idx_songs_order"]
        index_columns = published.execute("PRAGMA index_xinfo(idx_songs_order)").fetchall()
        if [(row[2], row[3]) for row in index_columns if row[5]] != [("popularity_score", 1), ("popularity_order", 0), ("sort_order", 0)]:
            raise ValueError("forward rehearsal has incorrect ordering index")
        if expected != actual:
            raise ValueError("forward rehearsal differs from release snapshot")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "incremental", "rehearse", "verify", "status"))
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--db-path", type=Path)
    parser.add_argument("--environment")
    parser.add_argument("--database")
    parser.add_argument("--status")
    args = parser.parse_args()
    if args.action == "prepare":
        prepare(args.db_path, args.directory, args.environment, args.database)
    elif args.action == "incremental":
        from tools.incremental_release import prepare_incremental
        prepare_incremental(args.directory)
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
