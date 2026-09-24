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
    # Heterogeneous rows make ordering errors observable, independently of SQL helpers.
    ordering = [raw_song(title, f"https://w.atwiki.jp/hmiku/pages/{101 + n}.html")
                for n, title in enumerate(("A", "BB", "CCCC", "DDDD", "EE"))]
    popularity_map = {s.raw_title: popularity() for s in songs}
    for song, order in zip(ordering, (2, 1, 1, 2, 1)):
        popularity_map[song.raw_title] = popularity(800, "ミリオン達成曲", order) if song == ordering[-1] else popularity(100, "殿堂入り", order)
    with temporary_db(songs + ordering, popularity_map) as path:
        for song in songs:
            save_song_detail_entry(path, song.url, {"page_title": "検証曲", "source_url": song.url, "reading": "",
                "credits": {"composer": ["検証作者"] + (["Straße", "ΟΣ"] if song == songs[-1] else [])}, "published_year": 2020,
                "introduction": ["結合テスト用のデータ"], "videos": {"niconico": [], "youtube": []},
                "related_videos": {"niconico": [], "youtube": []}})
        for song, year in zip(ordering, (2003, 2001, None, 2001, 2001)):
            save_song_detail_entry(path, song.url, {"page_title": song.raw_title, "source_url": song.url, "reading": "",
                "credits": {"composer": ["順序確認"]}, "published_year": year,
                "introduction": [], "videos": {"niconico": [], "youtube": []},
                "related_videos": {"niconico": [], "youtube": []}})
        with closing(sqlite3.connect(path)) as connection:
            export_atomic(connection, output, publish=True)
    subprocess.run(["./node_modules/.bin/wrangler", "d1", "execute", "integration", "--local",
                    "--config", "test/wrangler.integration.toml", "--persist-to", ".wrangler/integration",
                    "--file", str(output)], cwd=ROOT / "cloudflare/worker", check=True)


if __name__ == "__main__":
    main()
