#!/usr/bin/env python3
"""Check explicit per-page credit expectations against frozen HTML and a candidate DB."""
import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from vocaloid_title_search.database import connect_readonly, credit_people_rows, load_song_detail
from vocaloid_title_search.detail import COMPOUND_CREDIT_NAMES, clean_soup, extract_credits


def verify(root=ROOT, candidate=None, baseline=None, require_complete=False, atomic_names=()):
    errors = []
    outcomes = []
    try:
        reviews = json.loads((root / 'docs/completion/credit-reviews.json').read_text())
        ledger = json.loads((root / 'docs/completion/ledger.json').read_text())
        registered = {item['id'].removeprefix('CREDIT-REVIEW-') for item in ledger['issues']
                      if item['id'].startswith('CREDIT-REVIEW-')}
        if not isinstance(reviews, dict) or not reviews:
            raise ValueError('nonempty individual reviews required')
        if require_complete and set(reviews) != registered:
            errors.append(f'coverage: missing={sorted(registered - set(reviews))}, unexpected={sorted(set(reviews) - registered)}')
        for page, review in reviews.items():
            try:
                if not page.isdecimal() or page not in registered:
                    raise ValueError('review has no registered candidate')
                if (review['assessment'] not in {'source_valid', 'extractor_fix'}
                        or not review['rationale'].strip() or not isinstance(review['expected'], dict)):
                    raise ValueError('individual expectation and rationale required')
                source = (root / 'release/completion/credit-sources' / f'{page}.html').read_bytes()
                if hashlib.sha256(source).hexdigest() != review['source_sha256']:
                    raise ValueError('reviewed source changed')
                actual = extract_credits(clean_soup(source.decode()))
                if actual != review['expected']:
                    raise ValueError(f'parsed credits differ: {actual!r}')
                if candidate is not None:
                    stored = load_song_detail(candidate, f'https://w.atwiki.jp/hmiku/pages/{page}.html')
                    if stored is None or stored['credits'] != review['expected']:
                        raise ValueError('candidate differs from independent expectation')
                outcomes.append(page)
            except (KeyError, ValueError, TypeError, OSError) as exc:
                errors.append(f'{page}: {exc}')
        if atomic_names:
            if candidate is None:
                raise ValueError('atomic name scan requires candidate')
            errors.extend(check_atomic_names(root, candidate, reviews, atomic_names))
        if baseline is not None:
            if candidate is None:
                raise ValueError('baseline comparison requires candidate')
            errors.extend(check_preservation(candidate, baseline, set(reviews)))
    except (KeyError, ValueError, TypeError, OSError) as exc:
        errors.append(f'reviews: {exc}')
    return outcomes, errors



def check_atomic_names(root, candidate, reviews, names):
    errors = []
    for name in names:
        witnesses = []
        for page, review in reviews.items():
            if not any(name in values for values in review['expected'].values()):
                continue
            source = root / 'release/completion/credit-sources' / f'{page}.html'
            soup = clean_soup(source.read_text())
            if any(link.get_text('', strip=True) == name for link in soup.find_all('a')):
                witnesses.append(page)
        if not witnesses:
            errors.append(f'{name}: no individually reviewed single-link witness')
        if name in COMPOUND_CREDIT_NAMES and COMPOUND_CREDIT_NAMES[name] not in witnesses:
            errors.append(f'{name}: compound-name registry witness missing')
    if set(COMPOUND_CREDIT_NAMES) - set(names):
        errors.append('compound-name registry not fully checked')
    count = 0
    with closing(connect_readonly(candidate)) as connection:
        for url, payload in connection.execute('SELECT url,payload_json FROM song_details'):
            count += 1
            credits = json.loads(payload)['credits']
            for name in names:
                parts = re.split(r'[・/／]', name)
                if len(parts) < 2 or any(not part for part in parts):
                    raise ValueError('atomic name must contain separated nonempty parts')
                for role, values in credits.items():
                    if any(part in values for part in parts):
                        errors.append(f'{url}: {role} still contains fragments of {name}')
    if not count:
        errors.append('atomic-name scan covered zero details')
    print(f'atomic-name scan: details={count}, names={len(names)}, errors={len(errors)}')
    return errors


def check_preservation(candidate, baseline, pages):
    errors = []
    with closing(connect_readonly(baseline)) as before, \
            closing(connect_readonly(candidate)) as after:
        if after.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
            errors.append('candidate integrity failed')
        if after.execute('PRAGMA foreign_key_check').fetchall():
            errors.append('candidate foreign keys failed')
        for table in ('songs', 'metadata'):
            if before.execute(f'SELECT * FROM {table} ORDER BY 1').fetchall() != after.execute(f'SELECT * FROM {table} ORDER BY 1').fetchall():
                errors.append(f'{table}: unrelated values changed')
        old = {row[0]: row for row in before.execute('SELECT * FROM song_details')}
        new = {row[0]: row for row in after.execute('SELECT * FROM song_details')}
        if old.keys() != new.keys():
            errors.append('detail identity set changed')
        columns = [row[1] for row in before.execute('PRAGMA table_info(song_details)')]
        payload_index = columns.index('payload_json')
        expected_people = []
        for url, row in new.items():
            detail = json.loads(row[payload_index])
            expected_people.extend(credit_people_rows(url, detail))
            if url not in old:
                continue
            previous = json.loads(old[url][payload_index])
            page = url.rsplit('/', 1)[1].removesuffix('.html')
            if page in pages:
                previous.pop('credits', None)
                detail.pop('credits', None)
            if previous != detail:
                errors.append(f'{page}: unreviewed fields changed')
            if any(a != b for i, (a, b) in enumerate(zip(old[url], row)) if i != payload_index):
                errors.append(f'{page}: unrelated detail columns changed')
        actual_people = after.execute('SELECT song_url,role,name,normalized_name FROM song_credit_people').fetchall()
        if sorted(expected_people) != sorted(actual_people):
            errors.append('derived composer table differs from candidate credits')
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path)
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--require-complete', action='store_true')
    parser.add_argument('--atomic-name', action='append', default=[])
    args = parser.parse_args()
    outcomes, errors = verify(candidate=args.candidate, baseline=args.baseline, require_complete=args.require_complete, atomic_names=args.atomic_name)
    print(json.dumps({'reviewed': len(outcomes), 'pages': outcomes, 'errors': errors}, ensure_ascii=False))
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
