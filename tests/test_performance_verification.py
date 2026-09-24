"""Reject missing measurements and independently vary each acceptance dimension."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from tools.verify_performance import validate


class PerformanceVerificationTests(unittest.TestCase):
    def setUp(self):
        self.criteria = json.loads((Path(__file__).resolve().parents[1] / 'docs/completion/performance-criteria.json').read_text())
        self.sql = {'songs': 7868, 'rounds': 31, 'scenarios': [{'name': name, 'rows': 50, 'results_equal': True, 'baseline_ms': 5, 'current_ms': 4} for name in ('first page', 'length 5', 'year descending', 'deep page')]}
        paths = ['/health', '/api/stats', '/api/popularity-labels', '/api/search', '/api/search?length=5', '/api/search?composer=ryo', '/api/search?year=2021', '/api/search?sort=published_year_desc', '/api/search?page=20']
        self.d1 = {'requests': [{'path': path, 'run': run, 'results_equal': True, 'baseline_rows_read': 100, 'rows_read': 1 if run else 100, 'cache': 'hit' if run else 'miss'} for path in paths for run in (0, 1)], 'writes': [{'rows_written': value} for value in (10000, 7, 7)]}
        self.frontend = {name: [{'seconds': 1, 'rss_kib': 100000, 'js_gzip': 35000, 'css_gzip': 4000} for _ in range(3)] for name in ('baseline', 'current')}

    def test_complete_measurements_pass(self):
        self.assertEqual(validate(self.criteria, self.sql, self.d1, self.frontend), [])

    def test_zero_missing_mismatched_and_regressing_sql_fail(self):
        for field, value in [('rows', 0), ('results_equal', False), ('current_ms', 30), ('current_ms', float('nan')), ('current_ms', 7), ('baseline_ms', None)]:
            sql = deepcopy(self.sql); sql['scenarios'][0][field] = value
            with self.subTest(field=field, value=value): self.assertTrue(validate(self.criteria, sql, self.d1, self.frontend))
        for field, value in [('songs', 0), ('rounds', 1), ('scenarios', [])]:
            sql = deepcopy(self.sql); sql[field] = value
            self.assertTrue(validate(self.criteria, sql, self.d1, self.frontend))

    def test_missing_metrics_reads_cache_and_writes_fail(self):
        for field, value in [('rows_read', None), ('rows_read', 0), ('baseline_rows_read', None), ('rows_read', 101), ('results_equal', False)]:
            d1 = deepcopy(self.d1); d1['requests'][0][field] = value
            with self.subTest(field=field, value=value): self.assertTrue(validate(self.criteria, self.sql, d1, self.frontend))
        d1 = deepcopy(self.d1); d1['requests'] = []
        self.assertTrue(validate(self.criteria, self.sql, d1, self.frontend))
        d1 = deepcopy(self.d1); d1['requests'][-1]['cache'] = 'miss'
        self.assertTrue(validate(self.criteria, self.sql, d1, self.frontend))
        d1 = deepcopy(self.d1); d1['writes'][1]['rows_written'] = 500
        self.assertTrue(validate(self.criteria, self.sql, d1, self.frontend))

    def test_payload_time_memory_and_absent_builds_fail(self):
        for field, value in [('seconds', 2), ('rss_kib', 150000), ('js_gzip', 38000), ('css_gzip', 4700), ('seconds', None)]:
            frontend = deepcopy(self.frontend)
            for run in frontend['current']: run[field] = value
            with self.subTest(field=field, value=value): self.assertTrue(validate(self.criteria, self.sql, self.d1, frontend))
        frontend = deepcopy(self.frontend); frontend['current'] = []
        self.assertTrue(validate(self.criteria, self.sql, self.d1, frontend))
