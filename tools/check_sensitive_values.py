#!/usr/bin/env python3
"""Fail when tracked text files contain likely private operational values."""

from __future__ import annotations

import ipaddress
import re
import subprocess
import sys
from pathlib import Path


SKIPPED_SUFFIXES = {
    ".lock",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".sqlite3",
}
SKIPPED_PARTS = {
    ".git",
    ".wrangler",
    ".venv",
    ".uv-cache",
    "node_modules",
    "dist",
    "release",
    ".temp",
    "__pycache__",
}
ALLOWLISTED_DOMAINS = {
    "example.com",
    "www.example.com",
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "w.atwiki.jp",
    "astral.sh",
    "example.test",
    "ext.nicovideo.jp",
    "img.youtube.com",
    "nicovideo.cdn.nimg.jp",
    "youtube.com",
    "www.youtube.com",
    "youtu.be",
    "nicovideo.jp",
    "www.nicovideo.jp",
    "cloudflare.com",
    "api.cloudflare.com",
    "developers.cloudflare.com",
    "github.com",
}
ALLOWLISTED_DOMAIN_SUFFIXES = (
    ".example.com",
)

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")
URL_HOST_RE = re.compile(r"https?://([^/,\s'\"`]+)")
CONFIG_HOST_RE = re.compile(
    r"\b(?:DOMAIN|HEALTHCHECK_URL|VOCALOID_PUBLIC_BASE_URL|CORS_ORIGINS)\b"
    r"\s*=\s*['\"]?([^'\"\s]+)"
)
IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
SECRET_RE = re.compile(
    r"(?i)\b("
    r"api[_-]?key|token|secret|password|passwd|private[_-]?key|"
    r"cloudflare[_-]?api[_-]?token|github[_-]?token"
    r")\b\s*[:=]\s*['\"]?([A-Za-z0-9_./+=:-]{12,})"
)


def main() -> int:
    findings: list[str] = []
    for path in tracked_files():
        if should_skip(path):
            continue
        text = read_text(path)
        if text is None:
            continue
        findings.extend(scan_text(path, text))
    if findings:
        print("Sensitive value scan failed:", file=sys.stderr)
        for finding in findings:
            print(f"  {finding}", file=sys.stderr)
        return 1
    print("Sensitive value scan passed.")
    return 0


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )
    return [Path(line) for line in result.stdout.splitlines() if line]


def should_skip(path: Path) -> bool:
    if path.suffix.lower() in SKIPPED_SUFFIXES:
        return True
    return any(part in SKIPPED_PARTS for part in path.parts)


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except UnicodeDecodeError:
        return None


def scan_text(path: Path, text: str) -> list[str]:
    findings: list[str] = []
    findings.extend(scan_emails(path, text))
    findings.extend(scan_ips(path, text))
    findings.extend(scan_domains(path, text))
    findings.extend(scan_secrets(path, text))
    return findings


def scan_emails(path: Path, text: str) -> list[str]:
    findings = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for match in EMAIL_RE.finditer(line):
            if match.group(0).endswith("@example.com"):
                continue
            findings.append(f"{path}:{line_no}: email address `{match.group(0)}`")
    return findings


def scan_ips(path: Path, text: str) -> list[str]:
    findings = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for match in IPV4_RE.finditer(line):
            value = match.group(0)
            try:
                address = ipaddress.ip_address(value)
            except ValueError:
                continue
            if (
                address.is_private
                or address.is_loopback
                or address.is_reserved
                or address.is_unspecified
                or address.is_multicast
            ):
                continue
            findings.append(f"{path}:{line_no}: public IP address `{value}`")
    return findings


def scan_domains(path: Path, text: str) -> list[str]:
    findings = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for value in domain_candidates(line):
            normalized = normalize_host(value)
            if is_allowlisted_domain(normalized):
                continue
            findings.append(f"{path}:{line_no}: non-placeholder domain `{value}`")
    return findings


def domain_candidates(line: str) -> list[str]:
    values = []
    values.extend(match.group(1) for match in URL_HOST_RE.finditer(line))
    for match in CONFIG_HOST_RE.finditer(line):
        raw_value = match.group(1)
        values.extend(part.strip() for part in raw_value.split(",") if "." in part)
    return values


def normalize_host(value: str) -> str:
    host = value.strip().lower()
    if "://" in host:
        host = host.split("://", 1)[1]
    host = host.split("/", 1)[0]
    host = host.rsplit(":", 1)[0]
    return host


def is_allowlisted_domain(value: str) -> bool:
    if "$" in value or "." not in value:
        return True
    return value in ALLOWLISTED_DOMAINS or any(value.endswith(suffix) for suffix in ALLOWLISTED_DOMAIN_SUFFIXES)


def scan_secrets(path: Path, text: str) -> list[str]:
    findings = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if "replace-with-" in line or "example" in line:
            continue
        match = SECRET_RE.search(line)
        if match:
            findings.append(f"{path}:{line_no}: possible secret assignment `{match.group(1)}`")
    return findings


if __name__ == "__main__":
    raise SystemExit(main())
