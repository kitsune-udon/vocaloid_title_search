from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tools import check_docs


class DocumentationLinksTests(unittest.TestCase):
    def test_same_page_and_cross_page_anchors(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            page = root / "guide.md"
            page.write_text("# Guide\n[ok](#guide) [bad](#missing) [other](other.md#other)\n")
            with patch.object(check_docs, "ROOT", root), patch.object(check_docs, "DOCS_DIR", root):
                failures = check_docs.check_file_links(page, {"guide.md", "other.md"},
                    {"guide.md": {"guide"}, "other.md": {"other"}})
            self.assertEqual(failures, ["guide.md links to missing heading: #missing"])
