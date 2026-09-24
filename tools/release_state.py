"""Shared local artifact primitives; independent of release command orchestration."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile

from tools.export_d1_sql import TABLES


def atomic_write(path: Path, text: str) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save_manifest(directory: Path, manifest: dict) -> None:
    atomic_write(directory / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


def table_state(connection: sqlite3.Connection) -> dict:
    names = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    return {name: {
        "columns": connection.execute(f"PRAGMA table_info({name})").fetchall(),
        "rows": sorted(connection.execute(f"SELECT * FROM {name}").fetchall(), key=repr),
        "indexes": sorted(connection.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name=? AND sql IS NOT NULL", (name,)).fetchall()),
    } for name in TABLES if name in names}


def verify_artifacts(directory: Path, manifest: dict) -> None:
    for name, expected in manifest["artifacts"].items():
        if digest(directory / name) != expected:
            raise ValueError(f"release artifact changed after validation: {name}")
