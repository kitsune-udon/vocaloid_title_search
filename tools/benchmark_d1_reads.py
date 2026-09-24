#!/usr/bin/env python3
"""Compare Worker revisions using an isolated local D1; never contacts Cloudflare."""
from contextlib import closing
import argparse
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.export_d1_sql import PUBLICATION_KEY, export_atomic, publication_record
from tools.incremental_release import statements as incremental_statements
from datetime import datetime, timezone


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db-path', type=Path, default=ROOT / 'vocaloid_titles.sqlite3')
    parser.add_argument('--baseline-ref', default='HEAD')
    parser.add_argument('--baseline-source', type=Path, help='Saved Worker entry point for a working-tree baseline.')
    parser.add_argument('--output', type=Path, default=ROOT / 'release/performance/d1-reads.json')
    args = parser.parse_args()
    with TemporaryDirectory() as temporary:
        directory = Path(temporary)
        with closing(sqlite3.connect(args.db_path.resolve().as_uri() + '?mode=ro', uri=True)) as origin, closing(sqlite3.connect(directory / 'snapshot.sqlite3')) as snapshot:
            origin.backup(snapshot)
            export_atomic(snapshot, directory / 'data.sql', publish=True)
        statement = ''
        statements = []
        for line in (directory / 'data.sql').read_text().splitlines(keepends=True):
            statement += line
            if sqlite3.complete_statement(statement):
                statements.append(statement)
                statement = ''
        if statement.strip():
            raise ValueError('Incomplete export SQL')
        (directory / 'statements.json').write_text(json.dumps(statements))
        # Measure a metadata refresh with unchanged detail payloads on this same local D1.
        with closing(sqlite3.connect(':memory:')) as before, closing(sqlite3.connect(':memory:')) as after:
            before.executescript((directory / 'data.sql').read_text())
            before.backup(after)
            refreshed_at = datetime.now(timezone.utc).isoformat()
            after.executemany("UPDATE metadata SET value=? WHERE key=?", [
                (refreshed_at, f"video_metadata_{service}_fetched_at") for service in ('niconico', 'youtube')])
            after.execute("UPDATE metadata SET value=? WHERE key=?", (publication_record(after), PUBLICATION_KEY))
            after.commit()
            delta = incremental_statements(before, after)
            rollback = incremental_statements(after, before)
            def split_sql(script):
                result, pending = [], ''
                for line in script.splitlines(keepends=True):
                    pending += line
                    if sqlite3.complete_statement(pending):
                        result.append(pending)
                        pending = ''
                if pending.strip():
                    raise ValueError('Incomplete incremental SQL')
                return result
            (directory / 'incremental.json').write_text(json.dumps({'forward': split_sql(delta), 'rollback': split_sql(rollback)}))
        if args.baseline_source:
            # Bundle at its original location so relative imports keep working.
            subprocess.run([str(ROOT / 'cloudflare/worker/node_modules/.bin/esbuild'),
                            str(args.baseline_source.resolve()), '--bundle', '--format=esm',
                            f'--outfile={directory / "baseline.ts"}'], check=True)
        else:
            # Materialize the source tree: modular revisions need their relative imports.
            import tarfile
            from io import BytesIO
            archive = subprocess.check_output(['git', 'archive', args.baseline_ref, 'cloudflare/worker/src', 'shared'], cwd=ROOT)
            with tarfile.open(fileobj=BytesIO(archive)) as source:
                source.extractall(directory / 'baseline', filter='data')
            subprocess.run([str(ROOT / 'cloudflare/worker/node_modules/.bin/esbuild'),
                            str(directory / 'baseline/cloudflare/worker/src/index.ts'), '--bundle', '--format=esm',
                            f'--outfile={directory / "baseline.ts"}'], check=True)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['node', str(ROOT / 'tools/benchmark_d1_reads.mjs'), str(directory), str(args.output.resolve())], check=True, cwd=ROOT)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
