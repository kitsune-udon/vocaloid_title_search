import unittest
import urllib.error
from email.message import Message
from unittest.mock import patch

from vocaloid_title_search.http import HttpFetcher, HttpFetchPolicy


class FakeHeaders(dict):
    def get_content_charset(self) -> str:
        return "utf-8"


class FakeResponse:
    headers = FakeHeaders()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self) -> bytes:
        return "成功".encode("utf-8")


def http_error(status: int, retry_after: str | None = None) -> urllib.error.HTTPError:
    headers = Message()
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    return urllib.error.HTTPError("https://example.test/", status, "error", headers, None)


class HttpFetcherTests(unittest.TestCase):
    def test_retries_429_with_exponential_backoff(self) -> None:
        calls = []

        def opener(request, timeout):
            calls.append(request.full_url)
            if len(calls) == 1:
                raise http_error(429)
            return FakeResponse()

        fetcher = HttpFetcher(
            HttpFetchPolicy(request_interval=0, max_retries=1, backoff_base=2.5),
            opener=opener,
        )

        with patch("vocaloid_title_search.http.time.sleep") as sleep:
            body = fetcher.fetch_text(
                "https://example.test/page",
                timeout=1,
                user_agent="test-agent",
            )

        self.assertEqual(body, "成功")
        self.assertEqual(len(calls), 2)
        sleep.assert_called_once_with(2.5)

    def test_retry_after_header_overrides_backoff_and_is_capped(self) -> None:
        calls = 0

        def opener(request, timeout):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise http_error(503, retry_after="120")
            return FakeResponse()

        fetcher = HttpFetcher(
            HttpFetchPolicy(
                request_interval=0,
                max_retries=1,
                backoff_base=1,
                backoff_max=30,
            ),
            opener=opener,
        )

        with patch("vocaloid_title_search.http.time.sleep") as sleep:
            fetcher.fetch_text("https://example.test/page", timeout=1, user_agent="test-agent")

        sleep.assert_called_once_with(30)

    def test_does_not_retry_non_rate_limit_http_errors(self) -> None:
        def opener(request, timeout):
            raise http_error(404)

        fetcher = HttpFetcher(
            HttpFetchPolicy(request_interval=0, max_retries=3),
            opener=opener,
        )

        with patch("vocaloid_title_search.http.time.sleep") as sleep:
            with self.assertRaises(urllib.error.HTTPError):
                fetcher.fetch_text("https://example.test/page", timeout=1, user_agent="test-agent")

        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
