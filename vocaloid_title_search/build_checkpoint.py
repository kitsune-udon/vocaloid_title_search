"""Local build locking, checkpoint identity, and bounded reuse of fetched details."""
from contextlib import contextmanager, closing
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import json
from pathlib import Path
import sqlite3

from vocaloid_title_search.detail_contract import valid_detail
from vocaloid_title_search.database import DETAIL_SCHEMA_VERSION, connect_readonly, save_song_detail


@contextmanager
def build_lock(db_path):
    db_path = db_path.resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with db_path.with_name(f".{db_path.name}.build.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("another build is running for this database") from None
        yield


def extractor_fingerprint():
    digest = hashlib.sha256()
    for name in ("detail.py", "detail_videos.py", "detail_text.py"):
        path = Path(__file__).with_name(name)
        if path.exists():
            digest.update(path.read_bytes())
    return digest.hexdigest()


def corpus_fingerprint():
    digest = hashlib.sha256()
    for name in ("wiki.py", "models.py"):
        digest.update(name.encode() + b"\0")
        digest.update(Path(__file__).with_name(name).read_bytes())
    return digest.hexdigest()


def checkpoint_identity(args):
    return json.dumps({"source_url": args.source_url, "target": str(args.db_path.resolve()),
                       "schema": DETAIL_SCHEMA_VERSION, "extractor": extractor_fingerprint(),
                       "corpus": corpus_fingerprint(),
                       "video_metadata": args.with_video_metadata}, sort_keys=True)


def verify_checkpoint(path, args):
    with closing(connect_readonly(path)) as connection:
        metadata = dict(connection.execute("SELECT key, value FROM metadata"))
        if metadata.get("build_checkpoint") != checkpoint_identity(args):
            raise ValueError("checkpoint settings or extractor changed; move the checkpoint aside to start again")


def mark_checkpoint(path, args):
    with closing(sqlite3.connect(path)) as connection:
        connection.executemany("INSERT OR REPLACE INTO metadata VALUES (?, ?)", [
            ("build_checkpoint", checkpoint_identity(args)),
            ("detail_extractor_sha256", extractor_fingerprint()),
        ])
        connection.commit()


def reuse_details(previous, candidate, days):
    if not previous.exists() or not days:
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    count = 0
    with closing(connect_readonly(previous)) as source, closing(sqlite3.connect(candidate)) as target:
        metadata = dict(source.execute("SELECT key, value FROM metadata"))
        if metadata.get("detail_extractor_sha256") != extractor_fingerprint():
            return 0
        urls = {row[0] for row in target.execute("SELECT song_url FROM songs")}
        for url, payload, fetched, schema in source.execute("SELECT url, payload_json, source_fetched_at, schema_version FROM song_details"):
            if url not in urls or schema != DETAIL_SCHEMA_VERSION:
                continue
            try:
                timestamp = datetime.fromisoformat(fetched)
                detail = json.loads(payload)
                if (timestamp.tzinfo is None or not cutoff <= timestamp <= datetime.now(timezone.utc)
                        or not isinstance(detail, dict) or not valid_detail(detail, url, complete=True)):
                    continue
            except (ValueError, TypeError):
                continue
            save_song_detail(target, url, detail, fetched)
            count += 1
        target.commit()
    return count
