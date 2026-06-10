"""Shared command line option helpers."""

from __future__ import annotations

import argparse

from vocaloid_title_search.http import HttpFetchPolicy, configure_http_fetch

DEFAULT_TIMEOUT = 20.0
DEFAULT_REQUEST_INTERVAL = 0.2
DEFAULT_MAX_RETRIES = 2
DEFAULT_BACKOFF_BASE = 2.0
DEFAULT_BACKOFF_MAX = 30.0


def parser(description: str) -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("1以上の整数を指定してください。") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("1以上の整数を指定してください。")
    return parsed


def non_negative_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("0以上の数値を指定してください。") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("0以上の数値を指定してください。")
    return parsed


def positive_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("0より大きい数値を指定してください。") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("0より大きい数値を指定してください。")
    return parsed


def non_negative_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("0以上の整数を指定してください。") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("0以上の整数を指定してください。")
    return parsed


def add_http_options(
    target: argparse.ArgumentParser,
    *,
    request_interval_default: float = DEFAULT_REQUEST_INTERVAL,
) -> None:
    target.add_argument(
        "--timeout",
        type=positive_float,
        default=DEFAULT_TIMEOUT,
        help="HTTP取得のタイムアウト秒数。",
    )
    target.add_argument(
        "--request-interval",
        type=non_negative_float,
        default=request_interval_default,
        help="同一ホストへのHTTPリクエスト最小間隔秒数。",
    )
    target.add_argument(
        "--max-retries",
        type=non_negative_int,
        default=DEFAULT_MAX_RETRIES,
        help="HTTP 429/502/503/504 の最大リトライ回数。",
    )
    target.add_argument(
        "--backoff-base",
        type=non_negative_float,
        default=DEFAULT_BACKOFF_BASE,
        help="Retry-After がない場合の初回バックオフ秒数。",
    )
    target.add_argument(
        "--backoff-max",
        type=non_negative_float,
        default=DEFAULT_BACKOFF_MAX,
        help="バックオフ待機の最大秒数。",
    )


def configure_http_from_args(args: argparse.Namespace) -> None:
    configure_http_fetch(
        HttpFetchPolicy(
            request_interval=args.request_interval,
            max_retries=args.max_retries,
            backoff_base=args.backoff_base,
            backoff_max=args.backoff_max,
        )
    )
