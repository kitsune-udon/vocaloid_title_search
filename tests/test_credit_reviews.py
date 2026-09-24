from contextlib import closing, redirect_stdout
import io
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tests.helpers import raw_song, save_complete_detail, temporary_db
from tools.check_credit_reviews import verify, check_preservation, check_atomic_names


class CreditReviewTests(unittest.TestCase):
    def test_atomic_names_require_source_witness_and_no_database_fragments(self):
        with TemporaryDirectory() as directory, temporary_db([raw_song()]) as db:
            root = Path(directory)
            sources = root / 'release/completion/credit-sources'
            sources.mkdir(parents=True)
            source = sources / '82.html'
            source.write_text('<p>作曲：<a>作者・別名</a></p>')
            reviews = {'82': {'expected': {'composer': ['作者・別名']}}}
            with patch('tools.check_credit_reviews.COMPOUND_CREDIT_NAMES', {'作者・別名': '82'}), redirect_stdout(io.StringIO()):
                save_complete_detail(db, raw_song().url, {'credits': {'composer': ['作者・別名']}})
                self.assertEqual(check_atomic_names(root, db, reviews, ['作者・別名']), [])
                save_complete_detail(db, raw_song().url, {'credits': {'lyricist': ['作者', '別名']}})
                self.assertTrue(check_atomic_names(root, db, reviews, ['作者・別名']))
                save_complete_detail(db, raw_song().url, {'credits': {'composer': ['作者・別名']}})
                source.write_text('<p>作曲：作者・別名</p>')
                self.assertTrue(check_atomic_names(root, db, reviews, ['作者・別名']))
                with closing(sqlite3.connect(db)) as connection:
                    connection.execute('DELETE FROM song_details')
                    connection.commit()
                self.assertTrue(check_atomic_names(root, db, reviews, ['作者・別名']))

    def test_requires_individual_source_expectation_and_full_coverage(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / 'docs/completion'
            folder.mkdir(parents=True)
            sources = root / 'release/completion/credit-sources'
            sources.mkdir(parents=True)
            html = '<p>作曲：<a>検証作者</a></p><h3>曲紹介</h3>'.encode()
            (sources / '82.html').write_bytes(html)
            ledger = {'issues': [{'id': 'CREDIT-REVIEW-82'}, {'id': 'CREDIT-REVIEW-83'}]}
            (folder / 'ledger.json').write_text(json.dumps(ledger))
            review = {'expected': {'composer': ['検証作者']}, 'assessment': 'source_valid',
                      'rationale': 'explicit composer label and linked name',
                      'source_sha256': hashlib.sha256(html).hexdigest()}
            path = folder / 'credit-reviews.json'
            path.write_text(json.dumps({'82': review}))
            self.assertEqual(verify(root), (['82'], []))
            self.assertTrue(verify(root, require_complete=True)[1])
            for broken in ({}, {'82': {**review, 'expected': {}}},
                           {'82': {**review, 'rationale': ''}},
                           {'82': {**review, 'source_sha256': 'different'}},
                           {'84': review}):
                path.write_text(json.dumps(broken))
                self.assertTrue(verify(root)[1])
            path.write_text(json.dumps({'82': review}))
            with temporary_db([raw_song()]) as db:
                self.assertTrue(verify(root, candidate=db)[1])
                save_complete_detail(db, raw_song().url, {'credits': review['expected']})
                self.assertEqual(verify(root, candidate=db), (['82'], []))
            (sources / '82.html').write_bytes(html + b'changed')
            self.assertTrue(verify(root)[1])

    def test_preservation_rejects_unreviewed_changes_and_derived_table_corruption(self):
        with temporary_db([raw_song()]) as baseline:
            save_complete_detail(baseline, raw_song().url, {'credits': {'composer': ['作者']},
                                  'introduction': ['保存すべき紹介文']})
            candidate = baseline.with_name('candidate.sqlite3')
            shutil.copyfile(baseline, candidate)
            self.assertEqual(check_preservation(candidate, baseline, {'82'}), [])
            for sql in ("UPDATE metadata SET value='changed' WHERE key='schema_version'",
                        "UPDATE song_details SET source_fetched_at='changed'",
                        "UPDATE song_details SET payload_json=json_set(payload_json,'$.introduction',json('[]'))",
                        "DELETE FROM song_credit_people",
                        "DELETE FROM song_details"):
                shutil.copyfile(baseline, candidate)
                with closing(sqlite3.connect(candidate)) as connection:
                    connection.execute(sql)
                    connection.commit()
                self.assertTrue(check_preservation(candidate, baseline, {'82'}), sql)
