"""The source collector must not report an empty audit as successful."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
import unittest
from tools import audit_detail_sources


class DetailSourceAuditTests(unittest.TestCase):
    def test_empty_candidate_report_is_not_success(self):
        with TemporaryDirectory() as directory:
            empty = SimpleNamespace(total_issues=0, issues=[])
            with patch.object(audit_detail_sources, 'ROOT', Path(directory)), patch.object(audit_detail_sources, 'report_detail_quality', return_value=empty), patch.object(audit_detail_sources, 'HttpFetcher') as fetcher:
                with self.assertRaisesRegex(ValueError, 'zero targets'):
                    audit_detail_sources.collect()
                fetcher.assert_not_called()
