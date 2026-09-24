"""Exercise completion failures using real subprocess-generated verification records."""
from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from tools.completion_gate import AREAS, LEDGER, REGISTRY, REQUIRED_CHECKS, check, run_check, source_fingerprint


class CompletionGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        (self.root / '.gitignore').write_text('release/\n')
        (self.root / 'source.py').write_text('value = 1\n')
        (self.root / 'docs/completion').mkdir(parents=True)
        evidence = [{'check': 'all', 'finding': 'actual subprocess completed'}]
        requirements = [{'id': 'REQ-' + area.upper(), 'origin': 'goal', 'area': area,
                         'acceptance': 'observable behavior', 'verification': 'execute',
                         'limitations': 'synthetic fixture', 'issues': [], 'evidence': evidence}
                        for area in sorted(AREAS)]
        requirements.append({**requirements[0], 'id': 'REQ-GATE', 'area': 'ci_docs'})
        requirements[0]['issues'] = ['ISSUE-1']
        issue = {'id': 'ISSUE-1', 'title': 'failure scenario', 'severity': 'high', 'impact': 'wrong result',
                 'requirements': [requirements[0]['id']], 'reproduction': 'test input', 'status': 'fixed',
                 'acceptance': 'fixture produces expected result', 'verification': 'run fixture assertion', 'next_action': '',
                 'resolution': 'corrected behavior', 'rationale': 'independent assertion', 'evidence': evidence}
        checks = [{'id': id, 'command': [sys.executable, '-c', 'print("verified fixture")'],
                   'cwd': '.', 'target': 'fixture', 'requirements': [r['id'] for r in requirements]} for id in sorted(REQUIRED_CHECKS)]
        self.ledger = {'version': 1, 'requirements': requirements, 'issues': [issue], 'checks': checks}
        self.registry = {'version': 1, 'requirements': [{k:r[k] for k in ('id','origin','area','acceptance','verification','limitations')} for r in requirements],
                         'issues': [{k:issue[k] for k in ('id','title','requirements','reproduction','acceptance','verification')}], 'checks': checks}
        self.save()
        self.write(REGISTRY, self.registry)
        with redirect_stdout(io.StringIO()):
            for id in sorted(REQUIRED_CHECKS):
                self.assertEqual(run_check(self.root, id), 0)

    def write(self, name, value):
        (self.root / name).write_text(json.dumps(value))

    def save(self):
        self.write(LEDGER, self.ledger)

    def test_real_runner_records_valid_execution(self):
        self.assertEqual(check(self.root), [])
        record = json.loads((self.root / 'release/completion/all.json').read_text())
        self.assertEqual(record['exit_code'], 0)
        self.assertIn('verified fixture', (self.root / record['log']).read_text())

    def test_missing_malformed_and_empty_files_fail(self):
        for content in ('{', '{}', 'null', '[]'):
            with self.subTest(content=content):
                (self.root / LEDGER).write_text(content)
                self.assertTrue(check(self.root))
        (self.root / LEDGER).unlink()
        self.assertTrue(check(self.root))

    def test_open_and_unsupported_resolutions_fail(self):
        issue = self.ledger['issues'][0]
        for state in ('open', 'investigating', 'fixing', 'verification_pending', 'blocked', 'unknown'):
            issue['status'] = state
            self.save()
            self.assertTrue(any('unresolved' in e for e in check(self.root)))
        issue['status'] = 'not_needed'
        issue['rationale'] = ''
        self.save()
        self.assertTrue(any('rationale' in e for e in check(self.root)))
        issue['status'] = 'approved_deferred'
        issue['rationale'] = 'requires user decision'
        self.save()
        self.assertTrue(any('approval' in e for e in check(self.root)))

    def test_missing_duplicate_deleted_weakened_and_unlinked_items_fail(self):
        original = deepcopy(self.ledger)
        changes = [lambda d: d['issues'].clear(),
                   lambda d: d['issues'].append(deepcopy(d['issues'][0])),
                   lambda d: d['requirements'].pop(),
                   lambda d: d['requirements'][0].update(acceptance='weaker'),
                   lambda d: d['issues'][0].update(requirements=['missing']),
                   lambda d: d['issues'][0].update(evidence=[]),
                   lambda d: d['requirements'][0].update(evidence=[]),
                   lambda d: d['checks'].clear()]
        for mutate in changes:
            self.ledger = deepcopy(original)
            mutate(self.ledger)
            self.save()
            self.assertTrue(check(self.root))

    def test_failed_running_unknown_and_missing_records_fail(self):
        path = self.root / 'release/completion/all.json'
        original = json.loads(path.read_text())
        for changes in ({'exit_code': 1}, {'status': 'running'}, {'exit_code': None},
                        {'source_after': 'old'}, {'finished_at': 'invalid'}):
            path.write_text(json.dumps({**original, **changes}))
            self.assertTrue(any(e.startswith('all:') for e in check(self.root)))
        path.unlink()
        self.assertTrue(check(self.root))

    def test_untracked_source_change_and_log_tampering_invalidate_evidence(self):
        initial = source_fingerprint(self.root)
        (self.root / 'new.py').write_text('untracked = True\n')
        self.assertNotEqual(source_fingerprint(self.root), initial)
        self.assertTrue(any('source changed' in e for e in check(self.root)))
        (self.root / 'new.py').unlink()
        record = json.loads((self.root / 'release/completion/all.json').read_text())
        (self.root / record['log']).write_text('invented success')
        self.assertTrue(any('log changed' in e for e in check(self.root)))

    def test_runner_failure_is_recorded_as_failure(self):
        definition = next(c for c in self.ledger['checks'] if c['id'] == 'all')
        definition['command'] = [sys.executable, '-c', 'raise SystemExit(7)']
        self.save()
        with redirect_stdout(io.StringIO()):
            self.assertEqual(run_check(self.root, 'all'), 7)
        self.assertTrue(check(self.root))

    def test_duplicate_targets_missing_cycles_and_unresolved_fail(self):
        issue = self.ledger['issues'][0]
        for target, expected in [('missing', 'duplicate target missing'), ('ISSUE-1', 'duplicate reference cycle')]:
            issue['duplicate_of'] = target
            self.save()
            self.assertTrue(any(expected in e for e in check(self.root)))
        other = {**deepcopy(issue), 'id': 'ISSUE-2', 'status': 'open', 'next_action': 'investigate'}
        other.pop('duplicate_of')
        self.ledger['issues'].append(other)
        issue['duplicate_of'] = 'ISSUE-2'
        self.save()
        self.assertTrue(any('duplicate target unresolved' in e for e in check(self.root)))
        other['duplicate_of'] = 'ISSUE-1'
        self.save()
        self.assertTrue(any('duplicate reference cycle' in e for e in check(self.root)))

    def test_machine_report_preserves_ids_reasons_and_failure(self):
        from tools.completion_gate import completion_report
        self.assertEqual(completion_report([]), {'ok': True, 'error_count': 0, 'errors': []})
        report = completion_report(['ISSUE-1: unresolved (open)', 'all: missing log'])
        self.assertFalse(report['ok'])
        self.assertEqual(report['error_count'], 2)
        self.assertEqual(report['errors'][0], {'id': 'ISSUE-1', 'reason': 'unresolved (open)'})

    def test_runner_returns_failure_when_command_mutates_declared_input(self):
        data = self.root / 'release/candidate.txt'
        data.write_text('before')
        definition = next(c for c in self.ledger['checks'] if c['id'] == 'all')
        definition['inputs'] = ['release/candidate.txt']
        definition['command'] = [sys.executable, '-c', "from pathlib import Path; Path('release/candidate.txt').write_text('after')"]
        self.save()
        with redirect_stdout(io.StringIO()):
            self.assertEqual(run_check(self.root, 'all'), 1)
        record = json.loads((self.root/'release/completion/all.json').read_text())
        self.assertEqual(record['exit_code'],0)
        self.assertNotEqual(record['inputs_before'],record['inputs_after'])
        self.assertTrue(check(self.root))

    def test_environment_and_requirement_provenance_are_required(self):
        path = self.root/'release/completion/all.json'
        original = json.loads(path.read_text())
        self.assertTrue(original['environment_before']['python'])
        self.assertIn('ISSUE-1',original['related_issue_ids'])
        for values in ({'environment_after':{}}, {'environment_before':{}}, {'requirements':[]}):
            path.write_text(json.dumps({**original,**values}))
            self.assertTrue(any(error.startswith('all:') for error in check(self.root)))

    def test_success_exit_with_skipped_empty_or_zero_tests_is_not_success(self):
        definition = next(c for c in self.ledger['checks'] if c['id']=='all')
        for message in ('', 'Ran 0 tests in 0.000s', '2 passed, 1 skipped', 'OK (skipped=1)', '# tests 0', '# skipped 1'):
            with self.subTest(message=message):
                definition['command'] = [sys.executable,'-c',f'print({message!r})']
                self.save()
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(run_check(self.root,'all'),1)
                record=json.loads((self.root/'release/completion/all.json').read_text())
                self.assertEqual(record['exit_code'],0)
                self.assertTrue(record['validation_errors'])

    def test_future_execution_timestamp_is_rejected(self):
        path = self.root/'release/completion/all.json'
        record = json.loads(path.read_text())
        record['finished_at'] = '9999-01-01T00:00:00+00:00'
        path.write_text(json.dumps(record))
        self.assertTrue(any('invalid execution timestamps' in e for e in check(self.root)))

    def test_generated_input_changes_invalidate_evidence(self):
        data = self.root / 'release/candidate.txt'
        data.write_text('before')
        for definition in self.ledger['checks']:
            definition['inputs'] = ['release/candidate.txt']
        self.registry['checks'] = deepcopy(self.ledger['checks'])
        self.save()
        self.write(REGISTRY, self.registry)
        with redirect_stdout(io.StringIO()):
            for id in sorted(REQUIRED_CHECKS):
                run_check(self.root, id)
        self.assertEqual(check(self.root), [])
        data.write_text('after')
        self.assertTrue(any('inputs changed' in e for e in check(self.root)))

    def test_issue_acceptance_and_verification_cannot_be_omitted(self):
        for key in ('acceptance', 'verification', 'next_action'):
            original = self.ledger['issues'][0].pop(key)
            self.save()
            self.assertTrue(any('ISSUE-1:' in e for e in check(self.root)))
            self.ledger['issues'][0][key] = original

    def test_evidence_must_cover_the_requirement_it_claims(self):
        first = self.ledger['requirements'][0]['id']
        other = self.ledger['requirements'][1]['id']
        for definition in self.ledger['checks']:
            definition['requirements'] = [other]
        self.registry['checks'] = deepcopy(self.ledger['checks'])
        self.save(); self.write(REGISTRY, self.registry)
        with redirect_stdout(io.StringIO()):
            for id in sorted(REQUIRED_CHECKS): run_check(self.root, id)
        errors = check(self.root)
        self.assertTrue(any(e.startswith(first + ':') and 'scope' in e for e in errors))
        self.assertTrue(any(e.startswith('ISSUE-1:') and 'scope' in e for e in errors))

    def test_related_issue_ids_are_validated(self):
        path = self.root / 'release/completion/all.json'
        original = json.loads(path.read_text())
        for value in ([], ['missing'], ['ISSUE-1', 'ISSUE-1']):
            path.write_text(json.dumps({**original, 'related_issue_ids': value}))
            self.assertTrue(any(e.startswith('all:') for e in check(self.root)))

    def test_node_report_zero_skip_and_todo_are_rejected(self):
        from tools.completion_gate import log_validation_errors
        for output in ('ℹ tests 0', 'ℹ skipped 2', 'ℹ todo 1', '\x1b[32mℹ tests 0\x1b[0m'):
            with self.subTest(output=output): self.assertTrue(log_validation_errors(output))
        self.assertEqual(log_validation_errors('ℹ tests 24\nℹ skipped 0\nℹ todo 0'), [])

    def test_success_exit_cannot_hide_failed_test_summary(self):
        definition = next(c for c in self.ledger['checks'] if c['id'] == 'all')
        for output in ('FAILED (failures=1)', 'FAILED (errors=1)', 'ℹ fail 1', '# fail 2', '  1 failed (2s)', '=== 2 failed, 3 passed ==='):
            with self.subTest(output=output):
                definition['command'] = [sys.executable, '-c', f'print({output!r})']
                self.save()
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(run_check(self.root, 'all'), 1)
                record = json.loads((self.root / 'release/completion/all.json').read_text())
                self.assertEqual(record['exit_code'], 0)
                self.assertIn('verification reported failed tests', record['validation_errors'])
                self.assertTrue(check(self.root))
