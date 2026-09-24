#!/usr/bin/env python3
"""Run local performance comparisons against frozen, pre-measurement budgets."""
from __future__ import annotations
import argparse
import gzip
import json
import math
from pathlib import Path
import shutil
from statistics import median
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


def validate(criteria: dict, sql: dict, d1: dict, frontend: dict) -> list[str]:
    errors = []
    def require(condition, message):
        if not condition:
            errors.append(message)
    def positive(value):
        return type(value) in (int, float) and math.isfinite(value) and value > 0
    require(sql.get('songs', 0) > 0, 'SQL: no songs')
    require(sql.get('rounds', 0) >= criteria['sql']['rounds'], 'SQL: insufficient rounds')
    scenarios = sql.get('scenarios', [])
    require({s.get('name') for s in scenarios} == {'first page', 'length 5', 'year descending', 'deep page'} and len(scenarios) == 4, 'SQL: scenario coverage')
    for s in scenarios:
        label = 'SQL: ' + str(s.get('name'))
        require(s.get('results_equal') is True and s.get('rows', 0) > 0, label + ' missing results or equivalence')
        before, after = s.get('baseline_ms'), s.get('current_ms')
        if not positive(before) or not positive(after):
            errors.append(label + ' invalid timing'); continue
        budget = criteria['sql']
        require(after - before <= max(budget['noise_floor_ms'], before * budget['max_relative_regression']), label + ' regression')
        require(after <= budget['max_median_ms'], label + ' absolute latency')
    requests = d1.get('requests', [])
    expected_paths = {'/health', '/api/stats', '/api/popularity-labels', '/api/search', '/api/search?length=5', '/api/search?composer=ryo', '/api/search?year=2021', '/api/search?sort=published_year_desc', '/api/search?page=20'}
    require({(r.get('path'), r.get('run')) for r in requests} == {(path, run) for path in expected_paths for run in (0, 1)} and len(requests) == 18, 'D1: request coverage')
    for r in requests:
        label = 'D1: ' + str(r.get('path'))
        before, after = r.get('baseline_rows_read'), r.get('rows_read')
        require(r.get('results_equal') is True, label + ' equivalence missing')
        if not positive(before) or not positive(after):
            errors.append(label + ' missing read metrics'); continue
        require(after <= before * criteria['d1']['max_cold_read_ratio'], label + ' increased reads')
        if r.get('run') == 1 and r.get('path', '').startswith('/api/search'):
            require(r.get('cache') == 'hit' and after <= criteria['d1']['max_cached_rows_read'], label + ' cache budget')
    writes = d1.get('writes', [])
    require(len(writes) == 3, 'D1: write scenario coverage')
    if len(writes) == 3:
        full = writes[0].get('rows_written')
        require(positive(full), 'D1: missing full write metric')
        for item in writes[1:]:
            delta = item.get('rows_written')
            require(positive(delta) and positive(full) and delta <= full * criteria['d1']['max_incremental_write_ratio'], 'D1: incremental write budget')
    budget = criteria['frontend']
    for name in ('baseline', 'current'):
        runs = frontend.get(name, [])
        require(len(runs) == budget['rounds'], 'frontend: build round coverage ' + name)
        for run in runs:
            require(all(positive(run.get(key)) for key in ('seconds', 'rss_kib', 'js_gzip', 'css_gzip')), 'frontend: missing metrics ' + name)
    if errors:
        return errors
    before = {key: median(r[key] for r in frontend['baseline']) for key in frontend['baseline'][0]}
    after = {key: median(r[key] for r in frontend['current']) for key in frontend['current'][0]}
    for kind in ('js', 'css'):
        require(after[f'{kind}_gzip'] <= budget[f'max_{kind}_gzip_bytes'], f'frontend: absolute {kind} size')
        require(after[f'{kind}_gzip'] - before[f'{kind}_gzip'] <= budget[f'max_{kind}_gzip_increase_bytes'], f'frontend: increased {kind} size')
    require(after['seconds'] - before['seconds'] <= max(budget['build_time_noise_floor_seconds'], before['seconds'] * (budget['max_build_time_ratio'] - 1)), 'frontend: build time regression')
    require(after['rss_kib'] - before['rss_kib'] <= max(budget['rss_noise_floor_kib'], before['rss_kib'] * (budget['max_build_rss_ratio'] - 1)), 'frontend: build RSS regression')
    require(after['rss_kib'] <= budget['max_build_rss_kib'], 'frontend: absolute build RSS')
    return errors


def build_frontends(baseline: Path, rounds: int, temp: Path) -> dict:
    projects = {}
    for name, source in (('baseline', baseline), ('current', ROOT / 'frontend/src')):
        project = temp / name
        project.mkdir()
        shutil.copytree(source, project / 'src')
        for filename in ('package.json', 'vite.config.ts', 'index.html'):
            shutil.copy(ROOT / 'frontend' / filename, project / filename)
        shutil.copytree(ROOT / 'shared', temp / 'shared', dirs_exist_ok=True)
        (project / 'node_modules').symlink_to(ROOT / 'frontend/node_modules', target_is_directory=True)
        projects[name] = project
    results = {'baseline': [], 'current': []}
    for round_index in range(rounds):
        for name in (('baseline', 'current') if round_index % 2 == 0 else ('current', 'baseline')):
            project = projects[name]
            metrics = project / 'build-metrics.txt'
            subprocess.run(['/usr/bin/time', '-f', '%e %M', '-o', str(metrics), str(ROOT / 'frontend/node_modules/.bin/vite'), 'build'], cwd=project, check=True)
            seconds, rss = map(float, metrics.read_text().split())
            sizes = {kind: sum(len(gzip.compress(p.read_bytes(), mtime=0)) for p in (project / 'dist').rglob('*.' + kind)) for kind in ('js', 'css')}
            results[name].append({'seconds': seconds, 'rss_kib': rss, 'js_gzip': sizes['js'], 'css_gzip': sizes['css']})
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--criteria', type=Path, default=ROOT / 'docs/completion/performance-criteria.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'release/completion/performance-results.json')
    args = parser.parse_args()
    criteria = json.loads(args.criteria.read_text())
    with TemporaryDirectory() as directory:
        temp = Path(directory)
        subprocess.run([sys.executable, str(ROOT / 'tools/benchmark_search_sql.py'), '--db-path', str(args.candidate), '--baseline-source', str(args.baseline / 'worker/index.ts'), '--rounds', str(criteria['sql']['rounds']), '--output', str(temp / 'sql.json')], cwd=ROOT, check=True)
        subprocess.run([sys.executable, str(ROOT / 'tools/benchmark_d1_reads.py'), '--db-path', str(args.candidate), '--baseline-source', str(args.baseline / 'worker/index.ts'), '--output', str(temp / 'd1.json')], cwd=ROOT, check=True)
        frontend = build_frontends(args.baseline / 'frontend', criteria['frontend']['rounds'], temp)
        report = {'sql': json.loads((temp / 'sql.json').read_text()), 'd1': json.loads((temp / 'd1.json').read_text()), 'frontend': frontend}
        errors = validate(criteria, **report)
        report['errors'] = errors
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))
        return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
