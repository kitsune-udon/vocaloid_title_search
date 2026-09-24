#!/usr/bin/env python3
"""Compare Worker search SQL against a Git revision on read-only local SQLite."""
from __future__ import annotations

import argparse
import json
from contextlib import closing
from pathlib import Path
import re
import sqlite3
from statistics import median
import subprocess
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
WORKER = "cloudflare/worker/src/handlers.ts"


def search_sql(source: str, where: str, order: str) -> str:
    templates = [sql for sql in re.findall(r"`([^`]+)`", source)
                 if "songs.title," in sql and "LIMIT ? OFFSET ?" in sql]
    if len(templates) != 1:
        raise ValueError("Expected exactly one Worker search SQL template")
    sql = templates[0].replace("${filters.whereSql}", where).replace("${sqlOrderBy(params.sort)}", order)
    sql = sql.replace('${sqlOrderBy(params.sort).replaceAll("song_details.", "songs.")}', order.replace("song_details.", "songs."))
    if "${" in sql:
        raise ValueError("Unsupported SQL interpolation; update the benchmark")
    return sql


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, default=ROOT / "vocaloid_titles.sqlite3")
    parser.add_argument("--baseline-ref", default="HEAD")
    parser.add_argument("--baseline-source", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--rounds", type=int, default=15)
    args = parser.parse_args()
    if args.rounds < 1:
        parser.error("--rounds must be positive")
    sources = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", args.baseline_ref], cwd=ROOT, text=True).splitlines()
    baseline_path = WORKER if WORKER in sources else "cloudflare/worker/src/index.ts"
    baseline = args.baseline_source.read_text() if args.baseline_source else subprocess.check_output(["git", "show", f"{args.baseline_ref}:{baseline_path}"], cwd=ROOT, text=True)
    current = (ROOT / WORKER).read_text(encoding="utf-8")
    popularity = "popularity_score DESC, popularity_order, sort_order"
    scenarios = [
        ("first page", "", popularity, (50, 0)),
        ("length 5", "WHERE songs.title_length = ?", popularity, (5, 50, 0)),
        ("year descending", "", "song_details.published_year IS NULL, song_details.published_year DESC, " + popularity, (50, 0)),
        ("deep page", "", popularity, (50, 5000)),
    ]
    report = {"sqlite": sqlite3.sqlite_version, "rounds": args.rounds, "scenarios": []}
    with closing(sqlite3.connect(args.db_path.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        report["songs"] = connection.execute("SELECT COUNT(*) FROM songs").fetchone()[0]
        if report["songs"] < 1:
            raise ValueError("Empty benchmark database")
        print(f"SQLite {sqlite3.sqlite_version}; songs={connection.execute('SELECT COUNT(*) FROM songs').fetchone()[0]}; rounds={args.rounds}")
        print("scenario | baseline ms | current ms | speedup")
        for name, where, order, parameters in scenarios:
            queries = [search_sql(source, where, order) for source in (baseline, current)]
            results = [connection.execute(sql, parameters).fetchall() for sql in queries]
            if results[0] != results[1]:
                raise ValueError(f"Search results changed: {name}")
            samples: list[list[float]] = [[], []]
            for run in range(args.rounds):
                for index in (run % 2, 1 - run % 2):
                    start = perf_counter()
                    connection.execute(queries[index], parameters).fetchall()
                    samples[index].append((perf_counter() - start) * 1000)
            before, after = map(median, samples)
            report["scenarios"].append({"name": name, "results_equal": True, "rows": len(results[0]), "baseline_ms": before, "current_ms": after})
            print(f"{name} | {before:.3f} | {after:.3f} | {before / after:.2f}x")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
