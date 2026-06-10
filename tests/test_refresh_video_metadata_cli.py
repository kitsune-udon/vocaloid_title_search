import io
import unittest
from contextlib import redirect_stderr

from vocaloid_title_search.cli.common import (
    DEFAULT_BACKOFF_BASE,
    DEFAULT_BACKOFF_MAX,
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT,
)
from vocaloid_title_search.cli.refresh_video_metadata import (
    DEFAULT_VIDEO_METADATA_REQUEST_INTERVAL,
)
from vocaloid_title_search.cli.refresh_video_metadata import DEFAULT_VIDEO_METADATA_WORKERS
from vocaloid_title_search.cli.refresh_video_metadata import parse_args


class RefreshVideoMetadataCliTests(unittest.TestCase):
    def test_default_options_are_practical_for_metadata_refresh(self) -> None:
        args = parse_args([])

        self.assertEqual(args.workers, DEFAULT_VIDEO_METADATA_WORKERS)
        self.assertEqual(args.timeout, DEFAULT_TIMEOUT)
        self.assertEqual(args.request_interval, DEFAULT_VIDEO_METADATA_REQUEST_INTERVAL)
        self.assertEqual(args.max_retries, DEFAULT_MAX_RETRIES)
        self.assertEqual(args.backoff_base, DEFAULT_BACKOFF_BASE)
        self.assertEqual(args.backoff_max, DEFAULT_BACKOFF_MAX)

    def test_workers_sets_video_metadata_workers(self) -> None:
        args = parse_args(["--workers", "4"])

        self.assertEqual(args.workers, 4)

    def test_rejects_negative_request_interval(self) -> None:
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as context:
            parse_args(["--request-interval", "-1"])
        self.assertEqual(context.exception.code, 2)

    def test_rejects_zero_workers(self) -> None:
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as context:
            parse_args(["--workers", "0"])
        self.assertEqual(context.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
