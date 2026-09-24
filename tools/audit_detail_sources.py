#!/usr/bin/env python3
"""Collect every detail-quality candidate for review; never updates the source DB."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.release_state import atomic_write
from vocaloid_title_search.detail import parse_song_detail, clean_soup
from vocaloid_title_search.detail_quality import report_detail_quality, detail_issue_checks
from vocaloid_title_search.http import HttpFetcher, HttpFetchPolicy


def collect() -> int:
    database = ROOT / 'vocaloid_titles.sqlite3'
    directory = ROOT / 'release/completion/detail-sources'
    directory.mkdir(parents=True, exist_ok=True)
    report = report_detail_quality(database, limit=None)
    if report.total_issues < 1 or not report.issues:
        raise ValueError('No detail-quality candidates to audit; zero targets are not success')
    ledger = json.loads((ROOT / 'docs/completion/ledger.json').read_text())
    registered = {item['id'] for item in ledger['issues']}
    fetcher = HttpFetcher(HttpFetchPolicy(request_interval=0.5))
    results = []
    failures = []
    try:
        for number, issue in enumerate(report.issues, 1):
            page = issue.url.rsplit('/', 1)[-1].removesuffix('.html')
            ids = ['DATA-' + page + '-' + name for name in issue.checks]
            if any(id not in registered for id in ids):
                failures.append({'url': issue.url, 'error': 'candidate missing from ledger'})
                continue
            html_path = directory / (page + '.html')
            info_path = directory / (page + '.source.json')
            try:
                if not html_path.exists() or not info_path.exists():
                    html = fetcher.fetch_text(issue.url, timeout=15, user_agent='vocaloid-title-search/1.0')
                    atomic_write(html_path, html)
                    atomic_write(info_path, json.dumps({'url':issue.url,'fetched_at':datetime.now(timezone.utc).isoformat(),
                        'sha256':hashlib.sha256(html_path.read_bytes()).hexdigest()},ensure_ascii=False,indent=2))
                info = json.loads(info_path.read_text())
                if info['url'] != issue.url or info['sha256'] != hashlib.sha256(html_path.read_bytes()).hexdigest():
                    raise ValueError('cached source identity mismatch')
                html = html_path.read_text()
                detail = parse_song_detail(html, issue.url).to_dict()
                record = {'ids':ids,'title':issue.title,'url':issue.url,'source':info,
                    'before':issue.checks,'after':detail_issue_checks(json.dumps(detail),detail['published_year']),
                    'detail':detail,'review_status':'pending'}
                atomic_write(directory / (page + '.json'),json.dumps(record,ensure_ascii=False,indent=2))
                atomic_write(directory / (page + '.txt'),clean_soup(html).get_text('\n',strip=True))
                results.append({'page':page,'before':issue.checks,'after':record['after']})
            except Exception as exc:
                failures.append({'url':issue.url,'error':str(exc)})
            print(f'{number}/{len(report.issues)} collected={len(results)} failures={len(failures)}',flush=True)
    finally:
        fetcher.close()
    manifest = {'source_db_sha256':hashlib.sha256(database.read_bytes()).hexdigest(),
                'expected_rows':report.total_issues,'expected_candidates':sum(report.issue_counts.values()),
                'results':results,'failures':failures}
    atomic_write(directory/'manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    return int(bool(failures) or len(results) != report.total_issues)


if __name__ == '__main__':
    raise SystemExit(collect())
