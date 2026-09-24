#!/usr/bin/env python3
"""Run verification with source identity, and reject unsupported completion claims."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import json
import platform
import re
import shutil
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.release_state import atomic_write

LEDGER = 'docs/completion/ledger.json'
REGISTRY = 'docs/completion/registry.json'
AREAS = {'ui', 'api', 'data', 'database', 'operations', 'ci_docs', 'performance'}
REQUIRED_IDS = {'REQ-' + area.upper() for area in AREAS} | {'REQ-GATE'}
REQUIRED_CHECKS = {'all', 'docs', 'docs-build', 'ui', 'integration'}


def read_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def log_validation_errors(text: str) -> list[str]:
    errors = []
    text = re.sub(r"\x1b\[[0-9;]*m", "", text)
    if not text.strip():
        errors.append('verification produced no output')
    if re.search(r'Ran 0 tests\b|^[#ℹ] tests 0$|\b0 passed\b', text, re.MULTILINE):
        errors.append('verification reported zero tests')
    if re.search(r'\b[1-9][0-9]* skipped\b|skipped=[1-9][0-9]*|^[#ℹ] (?:skipped|todo) [1-9][0-9]*$', text, re.MULTILINE):
        errors.append('verification skipped required tests')
    if re.search(r'^\s*FAILED(?:\s*\(|\s*$)|^\s*[#ℹ] fail [1-9][0-9]*$|^\s*(?:=+\s*)?(?:[0-9]+ passed,\s*)?[1-9][0-9]* failed\b', text, re.MULTILINE):
        errors.append('verification reported failed tests')
    return errors


def execution_environment() -> dict:
    node = shutil.which('node')
    node_version = subprocess.check_output([node, '--version'], text=True, timeout=5).strip() if node else None
    return {'platform': platform.system(), 'architecture': platform.machine(),
            'python': sys.version, 'python_executable': str(Path(sys.executable).resolve()),
            'node_executable': str(Path(node).resolve()) if node else None, 'node': node_version}


def source_fingerprint(root: Path) -> str:
    names = subprocess.check_output(['git', 'ls-files', '-cz', '--others', '--exclude-standard'], cwd=root).split(b'\0')
    digest = hashlib.sha256()
    for raw in sorted(set(names) - {b''}):
        name = raw.decode()
        if name in {LEDGER, REGISTRY}:
            continue  # State is separately validated; it is not executable source.
        path = root / name
        digest.update(raw + b'\0')
        digest.update(path.read_bytes() if path.is_file() else b'<deleted>')
    return digest.hexdigest()


def input_fingerprints(root: Path, definition: dict) -> dict[str, str]:
    inputs = definition.get('inputs', [])
    if not isinstance(inputs, list) or not all(isinstance(name, str) for name in inputs):
        raise ValueError('inputs must be a list of repository paths')
    return {name: sha(safe_path(root, name)) for name in inputs}


def safe_path(root: Path, name: str) -> Path:
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('path escapes repository')
    return path


def index(items, label, errors):
    result = {}
    if not isinstance(items, list) or not items:
        errors.append(f'{label}: nonempty list required')
        return result
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get('id'), str) or not item['id']:
            errors.append(f'{label}: invalid ID')
            continue
        if item['id'] in result:
            errors.append(f"{label}: duplicate {item['id']}")
        result[item['id']] = item
    return result


def timestamp(value):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError('timezone required')
    return parsed


def check(root: Path) -> list[str]:
    errors = []
    try:
        ledger, registry = read_json(root / LEDGER), read_json(root / REGISTRY)
        if ledger.get('version') != 1 or registry.get('version') != 1:
            errors.append('schema: unsupported version')
        groups = {name: index(ledger.get(name), name, errors) for name in ('requirements', 'issues', 'checks')}
        for name in groups:
            registered = index(registry.get(name), 'registry.' + name, errors)
            for id, original in registered.items():
                current = groups[name].get(id)
                if current is None:
                    errors.append(f'{id}: registered item disappeared')
                elif any(current.get(key) != value for key, value in original.items()):
                    errors.append(f'{id}: registered definition changed; restore original or record an approved revision')
            for id in groups[name].keys() - registered.keys():
                errors.append(f'{id}: missing registration history')
        requirements, issues, checks = (groups[name] for name in ('requirements', 'issues', 'checks'))
        for id in REQUIRED_IDS - requirements.keys():
            errors.append(f'{id}: missing original requirement')
        for area in AREAS - {r.get('area') for r in requirements.values()}:
            errors.append(f'{area}: missing required area')
        for id in REQUIRED_CHECKS - checks.keys():
            errors.append(f'{id}: missing mandatory check')
        fingerprint = source_fingerprint(root)
        environment = execution_environment()
        verified = set()
        for id, definition in checks.items():
            try:
                if not isinstance(definition['command'], list) or not definition['command'] or not all(isinstance(x, str) for x in definition['command']):
                    raise ValueError('invalid command')
                if not definition.get('target'):
                    raise ValueError('target missing')
                if (not isinstance(definition.get('requirements'), list) or not definition['requirements']
                    or any(ref not in requirements for ref in definition['requirements'])):
                    raise ValueError('check requires valid requirement references')
                safe_path(root, definition['cwd'])
                record = read_json(safe_path(root, f'release/completion/{id}.json'))
                for field in ('command', 'cwd', 'target', 'requirements'):
                    if record[field] != definition[field]:
                        raise ValueError(f'{field} differs from registered check')
                related = [item['id'] for item in issues.values() if set(item['requirements']) & set(definition['requirements'])]
                if record.get('related_issue_ids') != related:
                    raise ValueError('related issue IDs changed or missing')
                if record.get('environment_before') != environment or record.get('environment_after') != environment:
                    raise ValueError('execution environment missing or changed')
                if record['status'] != 'finished' or type(record['exit_code']) is not int or record['exit_code'] != 0:
                    raise ValueError('verification not successfully finished')
                if record.get('inputs_before') != input_fingerprints(root, definition) or record.get('inputs_after') != input_fingerprints(root, definition):
                    raise ValueError('verification inputs changed')
                if record['source_before'] != fingerprint or record['source_after'] != fingerprint:
                    raise ValueError('source changed since verification')
                if (timestamp(record['finished_at']) < timestamp(record['started_at'])
                    or timestamp(record['finished_at']) > datetime.now(timezone.utc) + timedelta(seconds=5)):
                    raise ValueError('invalid execution timestamps')
                log = safe_path(root, record['log'])
                if sha(log) != record['log_sha256']:
                    raise ValueError('log changed or missing')
                validation_errors = log_validation_errors(log.read_text())
                if validation_errors:
                    raise ValueError('; '.join(validation_errors))
                verified.add(id)
            except (KeyError, TypeError, ValueError, OSError) as exc:
                errors.append(f'{id}: {exc}')
        for kind, items in (('requirement', requirements), ('issue', issues)):
            for id, item in items.items():
                fields = ('origin', 'area', 'acceptance', 'verification', 'limitations') if kind == 'requirement' else ('title', 'severity', 'impact', 'reproduction', 'acceptance', 'verification', 'status')
                for field in fields:
                    if not isinstance(item.get(field), str) or not item[field].strip():
                        errors.append(f'{id}: missing {field}')
                refs = item.get('issues' if kind == 'requirement' else 'requirements')
                targets = issues if kind == 'requirement' else requirements
                if not isinstance(refs, list) or (kind == 'issue' and not refs):
                    errors.append(f'{id}: missing references')
                else:
                    for ref in refs:
                        if ref not in targets:
                            errors.append(f'{id}: dangling reference {ref}')
                        elif id not in targets[ref].get('requirements' if kind == 'requirement' else 'issues', []):
                            errors.append(f'{id}: reference not reciprocal: {ref}')
                if kind == 'issue' and not isinstance(item.get('next_action'), str):
                    errors.append(f'{id}: next action field missing')
                evidence = item.get('evidence')
                if not isinstance(evidence, list) or not evidence:
                    errors.append(f'{id}: no evidence')
                else:
                    covered = set()
                    needed = {id} if kind == 'requirement' else set(refs or [])
                    for entry in evidence:
                        if not isinstance(entry, dict) or entry.get('check') not in verified or not entry.get('finding'):
                            errors.append(f'{id}: evidence has no current successful check/finding')
                        else:
                            scope = set(checks[entry['check']]['requirements']) & needed
                            if not scope:
                                errors.append(f'{id}: evidence scope does not cover this item')
                            covered.update(scope)
                    if needed - covered:
                        errors.append(f'{id}: evidence scope missing requirements: {sorted(needed - covered)}')
                if kind == 'issue':
                    status = item.get('status')
                    if status not in {'fixed', 'not_needed', 'approved_deferred'}:
                        errors.append(f'{id}: unresolved ({status})')
                        if not item.get('next_action'):
                            errors.append(f'{id}: next action missing')
                    else:
                        if not item.get('resolution') or not item.get('rationale'):
                            errors.append(f'{id}: resolution and rationale required')
                        if status == 'approved_deferred' and not item.get('approval_reference'):
                            errors.append(f'{id}: explicit user approval reference required')
        for id, item in issues.items():
            if 'duplicate_of' not in item:
                continue
            visited = {id}
            target = item['duplicate_of']
            while True:
                if not isinstance(target, str) or target not in issues:
                    errors.append(f'{id}: duplicate target missing')
                    break
                if target in visited:
                    errors.append(f'{id}: duplicate reference cycle')
                    break
                visited.add(target)
                destination = issues[target]
                if 'duplicate_of' in destination:
                    target = destination['duplicate_of']
                    continue
                if destination.get('status') not in {'fixed', 'not_needed', 'approved_deferred'}:
                    errors.append(f'{id}: duplicate target unresolved: {target}')
                break
        return errors
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        return errors + [f'completion state invalid: {exc}']


def run_check(root: Path, id: str) -> int:
    ledger = read_json(root / LEDGER)
    matches = [item for item in ledger['checks'] if item['id'] == id]
    if len(matches) != 1 or not id.replace('-', '').isalnum():
        raise ValueError('check ID must select exactly one registered command')
    definition = matches[0]
    requirement_ids = {item['id'] for item in ledger['requirements']}
    if (not isinstance(definition.get('requirements'), list) or not definition['requirements']
        or any(ref not in requirement_ids for ref in definition['requirements'])):
        raise ValueError('check requires valid requirement references')
    directory = root / 'release/completion'
    directory.mkdir(parents=True, exist_ok=True)
    log = directory / f'{id}-{uuid.uuid4().hex}.log'
    record = {**definition, 'environment_before': execution_environment(),
              'related_issue_ids': [item['id'] for item in ledger['issues']
                                    if set(item['requirements']) & set(definition['requirements'])],
              'started_at': datetime.now(timezone.utc).isoformat(),
              'source_before': source_fingerprint(root), 'inputs_before': input_fingerprints(root, definition), 'status': 'running',
              'exit_code': None, 'log': str(log.relative_to(root))}
    output = directory / f'{id}.json'
    atomic_write(output, json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    try:
        with log.open('w') as stream:
            process = subprocess.run(definition['command'], cwd=safe_path(root, definition['cwd']),
                                     stdout=stream, stderr=subprocess.STDOUT, check=False)
            record['exit_code'] = process.returncode
        record['status'] = 'finished'
    except BaseException:
        record['status'] = 'interrupted'
        raise
    finally:
        record['environment_after'] = execution_environment()
        record['finished_at'] = datetime.now(timezone.utc).isoformat()
        record['source_after'] = source_fingerprint(root)
        record['inputs_after'] = input_fingerprints(root, definition)
        record['log_sha256'] = sha(log) if log.exists() else ''
        record['validation_errors'] = log_validation_errors(log.read_text()) if log.exists() else ['log missing']
        atomic_write(output, json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    print(f"{id}: exit={record['exit_code']} log={record['log']}")
    if record['exit_code'] != 0:
        return record['exit_code']
    return record['exit_code'] if (not record['validation_errors'] and record['source_before'] == record['source_after']
                                   and record['inputs_before'] == record['inputs_after']
                                   and record['environment_before'] == record['environment_after']) else 1


def completion_report(errors: list[str]) -> dict:
    return {'ok': not errors, 'error_count': len(errors), 'errors': [
        {'id': error.split(':', 1)[0], 'reason': error.partition(':')[2].strip() or error}
        for error in errors
    ]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['check', 'run'])
    parser.add_argument('--id')
    parser.add_argument('--format', choices=['text', 'json'], default='text')
    args = parser.parse_args()
    if args.action == 'run':
        if not args.id:
            parser.error('run requires --id')
        return run_check(ROOT, args.id)
    errors = check(ROOT)
    if args.format == 'json':
        print(json.dumps(completion_report(errors), ensure_ascii=False))
    else:
        for error in errors:
            print(error)
        print(f'completion: {"FAIL" if errors else "PASS"}; errors={len(errors)}')
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
