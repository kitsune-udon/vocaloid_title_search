import io
import unittest
from contextlib import redirect_stderr

from vocaloid_title_search.cli.common import (
    DEFAULT_BACKOFF_BASE,
    DEFAULT_BACKOFF_MAX,
    DEFAULT_MAX_RETRIES,
    DEFAULT_REQUEST_INTERVAL,
    DEFAULT_TIMEOUT,
)
from vocaloid_title_search.cli.build_db import DEFAULT_BUILD_WORKERS
from vocaloid_title_search.cli.build_db import parse_args


class BuildDbCliTests(unittest.TestCase):
    def test_default_options_are_practical_for_full_build(self) -> None:
        args = parse_args([])

        self.assertEqual(args.workers, DEFAULT_BUILD_WORKERS)
        self.assertEqual(args.timeout, DEFAULT_TIMEOUT)
        self.assertEqual(args.request_interval, DEFAULT_REQUEST_INTERVAL)
        self.assertEqual(args.max_retries, DEFAULT_MAX_RETRIES)
        self.assertEqual(args.backoff_base, DEFAULT_BACKOFF_BASE)
        self.assertEqual(args.backoff_max, DEFAULT_BACKOFF_MAX)

    def test_workers_sets_detail_fetch_workers(self) -> None:
        args = parse_args(["--workers", "3"])

        self.assertEqual(args.workers, 3)

    def test_rejects_negative_request_interval(self) -> None:
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as context:
            parse_args(["--request-interval", "-1"])
        self.assertEqual(context.exception.code, 2)

    def test_rejects_zero_timeout(self) -> None:
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as context:
            parse_args(["--timeout", "0"])
        self.assertEqual(context.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
