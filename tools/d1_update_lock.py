#!/usr/bin/env python3
"""Own a non-expiring D1 update lock; recovery must explicitly release its owner."""
import argparse
import json
from pathlib import Path
import subprocess
import uuid

TABLE = '_vts_update_lock'
CREATE = f'''CREATE TABLE IF NOT EXISTS {TABLE} (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    owner TEXT NOT NULL,
    acquired_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)'''


def owner_token(value: str) -> str:
    token = uuid.UUID(value)
    if str(token) != value:
        raise ValueError('owner must be a canonical UUID')
    return value


def statement(action: str, owner: str) -> str:
    token = owner_token(owner)
    if action == 'acquire':
        return f"INSERT INTO {TABLE} (singleton, owner) VALUES (1, '{token}') RETURNING owner"
    if action == 'release':
        return f"DELETE FROM {TABLE} WHERE singleton=1 AND owner='{token}' RETURNING owner"
    raise ValueError('unsupported lock action')


def execute(worker: Path, database: str, remote: bool, sql: str):
    result = subprocess.run(
        [str(worker.resolve() / 'node_modules/.bin/wrangler'), 'd1', 'execute', database,
         '--remote' if remote else '--local', '--command', sql, '--json'],
        cwd=worker, capture_output=True, text=True, check=True,
    )
    payload = json.loads(result.stdout)
    if not isinstance(payload, list) or not payload or any(item.get('success') is not True for item in payload):
        raise ValueError('D1 did not report successful lock operation')
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['acquire', 'release'])
    parser.add_argument('--owner', required=True, type=owner_token)
    parser.add_argument('--database', required=True)
    parser.add_argument('--worker-dir', required=True, type=Path)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument('--remote', action='store_true')
    target.add_argument('--local', action='store_true')
    args = parser.parse_args()
    if args.action == 'acquire':
        execute(args.worker_dir, args.database, args.remote, CREATE)
    payload = execute(args.worker_dir, args.database, args.remote, statement(args.action, args.owner))
    owners = [row.get('owner') for item in payload for row in item.get('results', [])]
    if owners != [args.owner]:
        raise ValueError('lock ownership not confirmed; inspect before retrying')
    print(json.dumps({'action': args.action, 'owner': args.owner, 'confirmed': True}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
