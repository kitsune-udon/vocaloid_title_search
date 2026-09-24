#!/usr/bin/env python3
"""Verify every human-reviewed candidate against its frozen source and expected value."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from vocaloid_title_search.database import load_song_detail
from vocaloid_title_search.detail import parse_song_detail
from vocaloid_title_search.detail_quality import report_detail_quality


def reviewed_value(detail, field):
    if field == 'composer':
        return detail['credits'].get('composer', [])
    if field == 'niconico_primary_ids':
        return [video['id'] for video in detail['videos']['niconico']]
    return detail[field]


def main(root=ROOT, candidate=None):
    reviews = json.loads((root/'docs/completion/detail-reviews.json').read_text())
    report = report_detail_quality(root/'vocaloid_titles.sqlite3', limit=None)
    errors = []
    outcomes = []
    for issue in report.issues:
        page = issue.url.rsplit('/',1)[-1].removesuffix('.html')
        try:
            review = reviews[page]
            html = (root/'release/completion/detail-sources'/f'{page}.html').read_bytes()
            if hashlib.sha256(html).hexdigest() != review['source_sha256']:
                raise ValueError('source differs from reviewed HTML')
            if not review['rationale'].strip() or review['assessment'] not in {'source_absent','source_unspecified','extractor_fix'}:
                raise ValueError('individual review missing')
            detail = parse_song_detail(html.decode(), issue.url).to_dict()
            if reviewed_value(detail, review['field']) != review['expected']:
                raise ValueError('parsed value differs from independently reviewed expectation')
            if candidate is not None:
                stored = load_song_detail(candidate, issue.url)
                if stored is None or reviewed_value(stored, review['field']) != review['expected']:
                    raise ValueError('candidate database differs from reviewed expectation')
            outcomes.append({'page':page,'checks':issue.checks,'assessment':review['assessment']})
        except (KeyError, ValueError, OSError, TypeError) as exc:
            errors.append(f'{page}: {exc}')
    if not report.issues or len(outcomes) != report.total_issues:
        errors.append('complete candidate coverage not proven')
    for error in errors: print(error)
    print(json.dumps({'reviewed':len(outcomes),'expected':report.total_issues,'outcomes':outcomes},ensure_ascii=False))
    return int(bool(errors))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path)
    args = parser.parse_args()
    raise SystemExit(main(candidate=args.candidate))
