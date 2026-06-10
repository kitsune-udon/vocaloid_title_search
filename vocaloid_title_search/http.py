"""HTTP fetching helpers with polite rate limiting and retry backoff."""

from __future__ import annotations

import http.client
import atexit
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import threading
import time
import urllib.error
import urllib.parse
import urllib.request


RETRY_STATUS_CODES = {429, 502, 503, 504}


@dataclass(frozen=True)
class HttpFetchPolicy:
    request_interval: float = 0.2
    max_retries: int = 2
    backoff_base: float = 2.0
    backoff_max: float = 30.0


class HostRateLimiter:
    """Serialize requests per host with a minimum interval."""

    def __init__(self, interval_seconds: float) -> None:
        self.interval_seconds = max(0.0, interval_seconds)
        self._lock = threading.Lock()
        self._last_request_at: dict[str, float] = {}

    def wait(self, url: str) -> None:
        if self.interval_seconds <= 0:
            return

        host = urllib.parse.urlsplit(url).netloc or url
        while True:
            with self._lock:
                now = time.monotonic()
                last_request_at = self._last_request_at.get(host, now - self.interval_seconds)
                next_allowed_at = last_request_at + self.interval_seconds
                delay = next_allowed_at - now
                if delay <= 0:
                    self._last_request_at[host] = now
                    return
            time.sleep(delay)


class HttpFetcher:
    def __init__(
        self,
        policy: HttpFetchPolicy | None = None,
        opener=urllib.request.urlopen,
    ) -> None:
        self.policy = policy or HttpFetchPolicy()
        self._opener = opener
        self._rate_limiter = HostRateLimiter(self.policy.request_interval)
        self._thread_local = threading.local()

    def fetch_text(self, url: str, *, timeout: float, user_agent: str) -> str:
        request = urllib.request.Request(url, headers={"User-Agent": user_agent})
        for attempt in range(self.policy.max_retries + 1):
            self._rate_limiter.wait(url)
            try:
                if self._opener is urllib.request.urlopen:
                    return self.fetch_text_persistent(url, timeout=timeout, user_agent=user_agent)
                with self._opener(request, timeout=timeout) as response:
                    charset = response.headers.get_content_charset() or "utf-8"
                    return response.read().decode(charset, errors="replace")
            except urllib.error.HTTPError as exc:
                if not should_retry(exc, attempt, self.policy.max_retries):
                    raise
                time.sleep(retry_delay(exc, attempt + 1, self.policy))
        raise RuntimeError("unreachable retry state")

    def fetch_text_persistent(self, url: str, *, timeout: float, user_agent: str) -> str:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https":
            with urllib.request.urlopen(
                urllib.request.Request(url, headers={"User-Agent": user_agent}),
                timeout=timeout,
            ) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="replace")

        path = urllib.parse.urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
        connection = self.connection_for(parsed.netloc, timeout)
        try:
            connection.request(
                "GET",
                path,
                headers={
                    "Host": parsed.netloc,
                    "User-Agent": user_agent,
                    "Connection": "keep-alive",
                },
            )
            response = connection.getresponse()
            data = response.read()
            if response.status in {301, 302, 303, 307, 308}:
                location = response.headers.get("Location")
                self.close_connection(parsed.netloc)
                if location:
                    return self.fetch_text_persistent(
                        urllib.parse.urljoin(url, location),
                        timeout=timeout,
                        user_agent=user_agent,
                    )
            if response.status >= 400:
                raise urllib.error.HTTPError(
                    url,
                    response.status,
                    response.reason,
                    response.headers,
                    None,
                )
            charset = response.headers.get_content_charset() or "utf-8"
            return data.decode(charset, errors="replace")
        except (http.client.HTTPException, OSError):
            self.close_connection(parsed.netloc)
            raise

    def connection_for(self, netloc: str, timeout: float) -> http.client.HTTPSConnection:
        connections = getattr(self._thread_local, "connections", None)
        if connections is None:
            connections = {}
            self._thread_local.connections = connections
        connection = connections.get(netloc)
        if connection is None:
            connection = http.client.HTTPSConnection(netloc, timeout=timeout)
            connections[netloc] = connection
        return connection

    def close_connection(self, netloc: str) -> None:
        connections = getattr(self._thread_local, "connections", None)
        if not connections:
            return
        connection = connections.pop(netloc, None)
        if connection is not None:
            connection.close()

    def close(self) -> None:
        connections = getattr(self._thread_local, "connections", None)
        if not connections:
            return
        for connection in connections.values():
            connection.close()
        connections.clear()


def should_retry(
    exc: urllib.error.HTTPError,
    attempt: int,
    max_retries: int,
) -> bool:
    return exc.code in RETRY_STATUS_CODES and attempt < max_retries


def retry_delay(
    exc: urllib.error.HTTPError,
    retry_number: int,
    policy: HttpFetchPolicy,
) -> float:
    retry_after = retry_after_seconds(exc.headers.get("Retry-After") if exc.headers else None)
    if retry_after is not None:
        return min(retry_after, policy.backoff_max)
    return min(policy.backoff_base * (2 ** max(0, retry_number - 1)), policy.backoff_max)


def retry_after_seconds(raw_value: str | None) -> float | None:
    if not raw_value:
        return None
    value = raw_value.strip()
    if value.isdigit():
        return max(0.0, float(value))
    try:
        retry_at = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=timezone.utc)
    return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())


_default_fetcher = HttpFetcher()
atexit.register(_default_fetcher.close)


def configure_http_fetch(policy: HttpFetchPolicy) -> None:
    global _default_fetcher
    _default_fetcher.close()
    _default_fetcher = HttpFetcher(policy)
    atexit.register(_default_fetcher.close)


def fetch_text(url: str, *, timeout: float, user_agent: str) -> str:
    return _default_fetcher.fetch_text(url, timeout=timeout, user_agent=user_agent)
