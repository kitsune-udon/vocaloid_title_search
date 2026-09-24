"""Create a narrow, reversible metadata refresh without rewriting unchanged songs."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3

from tools.export_d1_sql import PUBLICATION_KEY, sql_literal, quote_identifier
from tools.release_state import atomic_write, digest, save_manifest, table_state, verify_artifacts


def statements(before: sqlite3.Connection, after: sqlite3.Connection) -> str:
    old, new = table_state(before), table_state(after)
    if old.keys() != new.keys() or len(old) != 4:
        raise ValueError('incremental release requires all four existing tables')
    for table in old:
        if old[table]['columns'] != new[table]['columns']:
            raise ValueError(f'incremental release cannot change columns: {table}')
        if table in ('songs', 'song_credit_people') and old[table]['rows'] != new[table]['rows']:
            raise ValueError(f'incremental release cannot change {table}')
    sql = [f'DELETE FROM metadata WHERE key={sql_literal(before, PUBLICATION_KEY)};']
    columns = [row[1] for row in old['song_details']['columns']]
    rows = [{row[0]: row for row in state['song_details']['rows']} for state in (old, new)]
    if rows[0].keys() != rows[1].keys():
        raise ValueError('incremental release cannot add or remove details')
    for key, row in rows[1].items():
        changed = [i for i, value in enumerate(row) if value != rows[0][key][i]]
        if any(columns[i] not in ('payload_json', 'fetched_at') for i in changed):
            raise ValueError('incremental release only supports video metadata refresh')
        if changed:
            assignments = ', '.join(f'{quote_identifier(columns[i])}={sql_literal(before, row[i])}' for i in changed)
            sql.append(f'UPDATE song_details SET {assignments} WHERE url={sql_literal(before, key)};')
    old_metadata, new_metadata = dict(old['metadata']['rows']), dict(new['metadata']['rows'])
    for key in old_metadata.keys() - new_metadata.keys() - {PUBLICATION_KEY}:
        sql.append(f'DELETE FROM metadata WHERE key={sql_literal(before, key)};')
    for key, value in new_metadata.items():
        if key != PUBLICATION_KEY and old_metadata.get(key) != value:
            sql.append(f'INSERT OR REPLACE INTO metadata (key,value) VALUES ({sql_literal(before, key)},{sql_literal(before, value)});')
    for table in old:
        old_indexes, new_indexes = dict(old[table]['indexes']), dict(new[table]['indexes'])
        for name in sorted(old_indexes.keys() | new_indexes.keys()):
            if old_indexes.get(name) == new_indexes.get(name):
                continue
            if name != 'idx_songs_order':
                raise ValueError(f'incremental release cannot change index: {name}')
            # Both directions must also work after any prefix of the other direction.
            sql.append(f'DROP INDEX IF EXISTS {quote_identifier(name)};')
            if name in new_indexes:
                sql.append(new_indexes[name] + ';')
    if PUBLICATION_KEY in new_metadata:
        sql.append(f'INSERT INTO metadata (key,value) VALUES ({sql_literal(before, PUBLICATION_KEY)},{sql_literal(before, new_metadata[PUBLICATION_KEY])});')
    return '\n'.join(sql) + '\n'


def prepare_incremental(directory: Path) -> None:
    manifest = json.loads((directory / 'manifest.json').read_text())
    verify_artifacts(directory, manifest)
    with closing(sqlite3.connect(':memory:')) as before, closing(sqlite3.connect(':memory:')) as after:
        before.executescript((directory / 'remote-before.sql').read_text())
        after.executescript((directory / 'new-vocaloid_titles.sql').read_text())
        forward, rollback = statements(before, after), statements(after, before)
        original = table_state(before)
        before.executescript(forward)
        if table_state(before) != table_state(after):
            raise ValueError('incremental result differs from complete release')
        before.executescript(rollback)
        if table_state(before) != original:
            raise ValueError('incremental rollback differs from original')
    for name in ('new-vocaloid_titles', 'rollback'):
        atomic_write(directory / f'{name}.full.sql', (directory / f'{name}.sql').read_text())
    atomic_write(directory / 'new-vocaloid_titles.sql', forward)
    atomic_write(directory / 'rollback.sql', rollback)
    manifest['mode'] = 'incremental-video-metadata'
    manifest['forward_verified'] = False
    manifest['rollback_verified'] = False
    for name in ('new-vocaloid_titles.sql', 'new-vocaloid_titles.full.sql', 'rollback.sql', 'rollback.full.sql', 'remote-before.sql'):
        manifest['artifacts'][name] = digest(directory / name)
    save_manifest(directory, manifest)
