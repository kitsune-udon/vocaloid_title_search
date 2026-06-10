#!/usr/bin/env python3
"""Static accessibility checks for the Vue frontend."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_VUE = ROOT / "frontend" / "src" / "App.vue"
STYLE_CSS = ROOT / "frontend" / "src" / "style.css"


def main() -> int:
    app = APP_VUE.read_text(encoding="utf-8")
    style = STYLE_CSS.read_text(encoding="utf-8")
    failures = [
        message
        for passed, message in checks(app, style)
        if not passed
    ]
    if failures:
        for failure in failures:
            print(f"Frontend accessibility check failed: {failure}")
        return 1
    print("Frontend accessibility check passed.")
    return 0


def checks(app: str, style: str) -> list[tuple[bool, str]]:
    return [
        ("a:focus-visible" in style, "focus-visible style for links is missing"),
        ("button:focus-visible" in style, "focus-visible style for buttons is missing"),
        ("input:focus-visible" in style, "focus-visible style for inputs is missing"),
        ("select:focus-visible" in style, "focus-visible style for selects is missing"),
        ('role="button"' in app and 'tabindex="0"' in app, "clickable result rows must be keyboard focusable"),
        ("@keydown.enter.prevent" in app, "result rows must handle Enter"),
        ("@keydown.space.prevent" in app, "result rows must handle Space"),
        (':aria-expanded="expandedUrls.has(row.url)"' in app, "result rows must expose expanded state"),
        ('aria-label="Wikiを開く"' in app, "Wiki icon link must have an accessible label"),
        ('aria-label="結果カードに表示する項目を選ぶ"' in app, "display options summary must have an accessible label"),
        ('aria-label="先頭ページへ"' in app, "first page button must have an accessible label"),
        ('aria-label="前のページへ"' in app, "previous page button must have an accessible label"),
        ('aria-label="次のページへ"' in app, "next page button must have an accessible label"),
        ('aria-label="最後のページへ"' in app, "last page button must have an accessible label"),
    ]


if __name__ == "__main__":
    raise SystemExit(main())
