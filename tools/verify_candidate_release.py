#!/usr/bin/env python3
"""Rehearse a candidate publication and exact baseline restoration locally."""
from contextlib import closing
import argparse
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.export_d1_sql import export_atomic
from tools.release_artifacts import prepare, rehearse, verify
from tools.release_state import digest
from vocaloid_title_search.database import connect_readonly


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, required=True)
    args = parser.parse_args()
    hashes = {str(path): digest(path) for path in (args.candidate, args.baseline)}
    parent = ROOT / 'release/completion'
    parent.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='candidate-release-', dir=parent))
    prepare(args.candidate, directory, 'local-rehearsal', 'isolated-memory-database')
    with closing(connect_readonly(args.baseline)) as baseline:
        with (directory / 'remote-before.sql').open('w') as stream:
            for statement in baseline.iterdump():
                stream.write(statement + '\n')
        export_atomic(baseline, directory / 'rollback.sql')
    rehearse(directory)
    verify(directory)
    if any(digest(Path(path)) != expected for path, expected in hashes.items()):
        raise ValueError('input database changed during rehearsal')
    print(json.dumps({'ok': True, 'environment': 'local SQLite',
                      'forward_verified': True, 'rollback_verified': True,
                      'inputs': hashes, 'artifacts': str(directory.relative_to(ROOT))}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
