#!/usr/bin/env python3
"""Check local documentation links and structure."""

from __future__ import annotations

import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"
ENTRYPOINTS = {DOCS_DIR / "index.md", DOCS_DIR / "README.md"}
MARKDOWN_LINK_PATTERN = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def main() -> int:
    failures: list[str] = []
    markdown_files = sorted(DOCS_DIR.glob("*.md"))
    known_files = {path.name for path in markdown_files}

    referenced_files: set[str] = {path.name for path in ENTRYPOINTS}
    anchors_by_file = {path.name: collect_anchors(path) for path in markdown_files}
    for path in markdown_files:
        failures.extend(check_file_links(path, known_files, anchors_by_file))
        failures.extend(check_duplicate_headings(path))
        referenced_files.update(local_markdown_targets(path))

    orphaned = sorted(known_files - referenced_files)
    if orphaned:
        failures.append(
            "docs files are not linked from any local markdown file: "
            + ", ".join(orphaned)
        )

    if failures:
        for failure in failures:
            print(f"Documentation check failed: {failure}")
        return 1
    print("Documentation check passed.")
    return 0


def check_file_links(
    path: Path,
    known_files: set[str],
    anchors_by_file: dict[str, set[str]],
) -> list[str]:
    failures: list[str] = []
    for target in markdown_links(path):
        link = clean_link_target(target)
        if not link or is_external_or_special(link):
            continue
        target_path, fragment = split_link(link)
        if target_path in ("", "."):
            target_file = path.name
        else:
            resolved = (path.parent / target_path).resolve()
            try:
                resolved.relative_to(DOCS_DIR.resolve())
            except ValueError:
                continue
            target_file = resolved.name
        if not target_file.endswith(".md"):
            continue
        if target_file not in known_files:
            failures.append(f"{path.relative_to(ROOT)} links to missing docs file: {target}")
            continue
        if fragment and fragment not in anchors_by_file[target_file]:
            failures.append(
                f"{path.relative_to(ROOT)} links to missing heading: {target}"
            )
    return failures


def check_duplicate_headings(path: Path) -> list[str]:
    headings = [slugify(title) for _, title in headings_in(path)]
    duplicates = sorted(slug for slug, count in Counter(headings).items() if count > 1)
    if not duplicates:
        return []
    return [f"{path.relative_to(ROOT)} has duplicate headings: {', '.join(duplicates)}"]


def local_markdown_targets(path: Path) -> set[str]:
    targets: set[str] = set()
    for target in markdown_links(path):
        link = clean_link_target(target)
        if not link or is_external_or_special(link):
            continue
        target_path, _ = split_link(link)
        if not target_path:
            targets.add(path.name)
            continue
        resolved = (path.parent / target_path).resolve()
        try:
            resolved.relative_to(DOCS_DIR.resolve())
        except ValueError:
            continue
        if resolved.suffix == ".md":
            targets.add(resolved.name)
    return targets


def collect_anchors(path: Path) -> set[str]:
    anchors = {""}
    for _, title in headings_in(path):
        anchors.add(slugify(title))
    return anchors


def headings_in(path: Path) -> list[tuple[int, str]]:
    results: list[tuple[int, str]] = []
    in_fence = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = HEADING_PATTERN.match(line)
        if match:
            results.append((len(match.group(1)), strip_inline_markup(match.group(2))))
    return results


def markdown_links(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return [match.group(1).strip() for match in MARKDOWN_LINK_PATTERN.finditer(text)]


def clean_link_target(target: str) -> str:
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    return target.strip()


def is_external_or_special(link: str) -> bool:
    return (
        "://" in link
        or link.startswith("mailto:")
        or link.startswith("#")
        or link.startswith("/")
    )


def split_link(link: str) -> tuple[str, str]:
    parsed = urlsplit(link)
    return unquote(parsed.path), unquote(parsed.fragment)


def strip_inline_markup(value: str) -> str:
    value = re.sub(r"`([^`]+)`", r"\1", value)
    value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
    value = value.strip(" #")
    return value


def slugify(value: str) -> str:
    value = strip_inline_markup(value).lower()
    value = re.sub(r"[^\w\-\u3040-\u30ff\u3400-\u9fff ]+", "", value)
    value = re.sub(r"\s+", "-", value.strip())
    return value


if __name__ == "__main__":
    raise SystemExit(main())
