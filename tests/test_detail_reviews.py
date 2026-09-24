from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tools.check_detail_reviews import main
from vocaloid_title_search.detail_quality import DetailQualityIssue, DetailQualityReport


class DetailReviewTests(unittest.TestCase):
    def test_missing_changed_or_wrong_review_is_rejected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'docs/completion').mkdir(parents=True)
            (root/'release/completion/detail-sources').mkdir(parents=True)
            html = b'<h3>\xe6\x9b\xb2\xe7\xb4\xb9\xe4\xbb\x8b</h3><p>hello world</p><h3>lyrics</h3>'
            source = root/'release/completion/detail-sources/1.html'
            source.write_bytes(html)
            review = {'source_sha256':hashlib.sha256(html).hexdigest(),'field':'introduction',
                      'expected':['hello world'],'assessment':'extractor_fix','rationale':'source paragraph confirmed'}
            report = DetailQualityReport(root/'db', 1, 1, {'missing_introduction':1},
                       [DetailQualityIssue('test','https://w.atwiki.jp/hmiku/pages/1.html',['missing_introduction'])])
            path = root/'docs/completion/detail-reviews.json'
            with patch('tools.check_detail_reviews.report_detail_quality',return_value=report), redirect_stdout(io.StringIO()):
                path.write_text(json.dumps({'1':review}))
                self.assertEqual(main(root),0)
                with patch('tools.check_detail_reviews.load_song_detail', return_value={'introduction':['hello world']}):
                    self.assertEqual(main(root, candidate=root/'candidate.sqlite3'),0)
                for candidate in (None, {'introduction':[]}, {}):
                    with patch('tools.check_detail_reviews.load_song_detail', return_value=candidate):
                        self.assertEqual(main(root, candidate=root/'candidate.sqlite3'),1)
                for broken in ({}, {'1':{**review,'expected':[]}}, {'1':{**review,'source_sha256':'changed'}},
                               {'1':{**review,'rationale':''}}, {'1':{**review,'assessment':'unreviewed'}}):
                    path.write_text(json.dumps(broken))
                    self.assertEqual(main(root),1)
                path.write_text(json.dumps({'1':review}))
                source.write_bytes(html+b'changed')
                self.assertEqual(main(root),1)

    def test_empty_candidate_report_is_not_completion(self):
        with TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'docs/completion').mkdir(parents=True)
            (root/'docs/completion/detail-reviews.json').write_text('{}')
            with patch('tools.check_detail_reviews.report_detail_quality',return_value=DetailQualityReport(root/'db',0)), redirect_stdout(io.StringIO()):
                self.assertEqual(main(root),1)
