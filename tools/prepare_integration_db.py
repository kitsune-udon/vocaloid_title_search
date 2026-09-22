#!/usr/bin/env python3
"""Seed a separate local D1 using synthetic data; never reads the public DB/config."""
from contextlib import closing
from pathlib import Path
import sqlite3
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests.helpers import raw_song, popularity, temporary_db
from vocaloid_title_search.database import save_song_detail_entry
from tools.export_d1_sql import export_atomic


def main():
    output = ROOT / "release/integration/fixture.sql"
    output.parent.mkdir(parents=True, exist_ok=True)
    songs = [raw_song("検証" + chr(0x4e00 + n), f"https://w.atwiki.jp/hmiku/pages/{n}.html") for n in range(1, 52)]
    with temporary_db(songs, {s.raw_title: popularity() for s in songs}) as path:
        for song in songs:
            save_song_detail_entry(path, song.url, {"page_title": "検証曲", "source_url": song.url,
                "credits": {"composer": ["検証作者"]}, "published_year": 2020,
                "introduction": ["結合テスト用のデータ"], "videos": {"niconico": [], "youtube": []},
                "related_videos": {"niconico": [], "youtube": []}})
        with closing(sqlite3.connect(path)) as connection:
            export_atomic(connection, output)
    subprocess.run(["./node_modules/.bin/wrangler", "d1", "execute", "integration", "--local",
                    "--config", "test/wrangler.integration.toml", "--persist-to", ".wrangler/integration",
                    "--file", str(output)], cwd=ROOT / "cloudflare/worker", check=True)


if __name__ == "__main__":
    main()
