"""Structured detail extraction from Hatsune Miku Wiki song pages."""

import re
import urllib.parse
from html import unescape
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field

from bs4 import BeautifulSoup

from vocaloid_title_search.http import fetch_text as http_fetch_text


USER_AGENT = "vocaloid-title-search/1.0"
CREDIT_LABELS = {
    "作詞": "lyricist",
    "作曲": "composer",
    "編曲": "arranger",
    "唄": "vocalist",
    "絵": "illustrator",
    "イラスト": "illustrator",
    "Illust": "illustrator",
    "ILLUST": "illustrator",
    "illust": "illustrator",
    "Illustration": "illustrator",
    "ILLUSTRATION": "illustrator",
    "illustration": "illustrator",
    "Illustrator": "illustrator",
    "ILLUSTRATOR": "illustrator",
    "illustrator": "illustrator",
    "動画": "video",
    "動画制作": "video",
    "映像": "video",
    "映像制作": "video",
    "MV": "video",
    "PV": "video",
    "Movie": "video",
    "MOVIE": "video",
    "movie": "video",
    "調声": "tuning",
}
SECTION_END_MARKERS = {"歌詞", "関連動画", "コメント"}
SUBSECTION_MARKER_LINE = "+"
EXCLUDED_VIDEO_SECTION_HEADINGS = {"英語版"}
DISCARDED_CREDIT_VALUES = {
    "+",
    "＋",
    "・",
    "原曲",
    "関連動画",
    "Best Friend Remix",
    "詳細",
}
LINK_NOTE_LABELS = {
    "twitter",
    "twitter.com",
    "x",
    "x.com",
    "ホームページ",
    "hp",
    "web",
    "website",
    "公式サイト",
    "youtube",
    "ニコニコ動画",
    "ニコニコ",
    "piapro",
    "pixiv",
    "instagram",
}
COMPACT_LINK_NOTE_TOKENS = (
    "twitter",
    "twitter.com",
    "instagram",
    "instagram.com",
    "youtube",
    "youtube.com",
    "pixiv",
    "pixiv.net",
    "piapro",
    "niconico",
    "ニコニコ",
    "ホームページ",
    "公式サイト",
    "site",
    "hp",
    "fanbox",
    "skeb",
    "x",
)
NICONICO_ID_PATTERN = re.compile(
    r"(?:nicovideo\.jp/watch/|ext\.nicovideo\.jp/thumb/)((?:sm|nm|so)\d+)"
)
YOUTUBE_ID_PATTERN = re.compile(
    r"(?:youtube\.com/(?:watch\?v=|embed/)|youtu\.be/)([A-Za-z0-9_-]{11})"
)
IFRAME_SRC_PATTERN = re.compile(r"<iframe\b[^>]*\bsrc=[\"']([^\"']+)[\"']", re.I)
LINK_HREF_PATTERN = re.compile(r"<a\b[^>]*\bhref=[\"']([^\"']+)[\"']", re.I)
VideoMap = dict[str, list[dict[str, str]]]


@dataclass(frozen=True)
class SongDetail:
    page_title: str
    reading: str = ""
    published_year: int | None = None
    credits: dict[str, list[str]] = field(default_factory=dict)
    introduction: list[str] = field(default_factory=list)
    videos: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    related_videos: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    source_url: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def fetch_song_detail(
    url: str,
    timeout: float = 10.0,
) -> dict[str, object]:
    page_html = fetch_text(url, timeout=timeout)
    return parse_song_detail(page_html, url).to_dict()


def parse_song_detail(
    page_html: str,
    source_url: str,
) -> SongDetail:
    soup = clean_soup(page_html)
    video_html, related_video_html = split_video_sections(page_html)
    main_video_html = remove_excluded_video_sections(video_html)
    main_link_videos = extract_videos(
        main_video_html,
        include_iframes=False,
        include_links=True,
    )
    related_section_videos = extract_videos(related_video_html)
    return SongDetail(
        page_title=extract_page_title(soup),
        reading=extract_reading(soup),
        published_year=extract_published_year(soup),
        credits=extract_credits(soup),
        introduction=extract_introduction(soup),
        videos=extract_videos(
            main_video_html,
            include_iframes=True,
            include_links=False,
        ),
        related_videos=merge_video_maps(main_link_videos, related_section_videos),
        source_url=source_url,
    )


def is_allowed_wiki_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    return (
        parsed.scheme == "https"
        and parsed.netloc == "w.atwiki.jp"
        and re.fullmatch(r"/hmiku/pages/\d+\.html", parsed.path) is not None
    )


def fetch_text(url: str, timeout: float = 10.0) -> str:
    return http_fetch_text(url, timeout=timeout, user_agent=USER_AGENT)


def clean_soup(page_html: str, *, remove_media: bool = True) -> BeautifulSoup:
    soup = BeautifulSoup(page_html, "lxml")
    remove_noise_nodes(soup, remove_media=remove_media)
    return soup


def remove_noise_nodes(soup: BeautifulSoup, *, remove_media: bool = True) -> None:
    tags = ["script", "style", "noscript"]
    if remove_media:
        tags.append("iframe")
    for node in soup(tags):
        node.decompose()


def extract_page_title(soup: BeautifulSoup) -> str:
    if not soup.title:
        return ""
    title = clean_text(soup.title.get_text(" "))
    return re.sub(r"\s*-\s*初音ミク Wiki.*$", "", title).strip()


def extract_published_year(soup: BeautifulSoup) -> int | None:
    years: list[int] = []
    for link in soup.find_all("a", href=True):
        text = clean_text(link.get_text(""))
        match = re.fullmatch(r"(\d{4})年", text)
        if not match:
            continue
        href = urllib.parse.unquote(str(link.get("href", "")))
        if "/hmiku/tag/" not in href:
            continue
        year = int(match.group(1))
        if 2004 <= year <= 2100:
            years.append(year)
    return min(years, default=None)


def extract_credits(soup: BeautifulSoup) -> dict[str, list[str]]:
    credits: dict[str, list[str]] = {}
    lines = credit_section_lines(soup)
    index = 0
    while index < len(lines):
        if line_starts_alternate_version_subsection(lines, index):
            break

        label_text, value = credit_label_and_value(lines[index])
        if not label_text:
            index += 1
            continue

        field_names = credit_field_names(label_text)
        if not field_names:
            index += 1
            continue

        values: list[str] = []
        if value:
            values.extend(split_credit_text(value))

        index += 1
        while index < len(lines):
            line = lines[index]
            if line in SECTION_END_MARKERS or line == "曲紹介":
                break
            if line_starts_alternate_version_subsection(lines, index):
                index = len(lines)
                break
            if is_label_boundary_line(line) and parenthesis_balance("".join(values)) <= 0:
                break
            values.extend(split_credit_text(line))
            index += 1

        clean_values = normalize_credit_values(values)
        if clean_values:
            add_credit_values(credits, field_names, clean_values)
    return credits


def line_starts_alternate_version_subsection(lines: list[str], index: int) -> bool:
    if clean_text(lines[index]) not in {SUBSECTION_MARKER_LINE, "＋"}:
        return False
    next_line = next_useful_line(lines, index + 1)
    return bool(next_line and is_alternate_version_heading(next_line))


def next_useful_line(lines: list[str], start: int) -> str:
    for line in lines[start:]:
        text = clean_text(line)
        if text:
            return text
    return ""


def is_alternate_version_heading(line: str) -> bool:
    text = clean_text(line)
    return bool(re.search(r"(?:Remix|RMX|Reloaded|ver\.|Ver\.|版)$", text))


def credit_label_and_value(line: str) -> tuple[str, str]:
    label_text, value = split_credit_label(line)
    if label_text:
        return label_text, value
    text = clean_text(line)
    if standalone_credit_field_names(text):
        return text, ""
    return "", ""


def credit_section_lines(soup: BeautifulSoup) -> list[str]:
    lines = useful_lines(soup.get_text("\n"))
    section_end = find_credit_section_end(lines) or len(lines)
    section_start = find_credit_section_start(lines, section_end)
    return lines[section_start:section_end]


def add_credit_values(
    credits: dict[str, list[str]],
    field_names: list[str],
    values: list[str],
) -> None:
    for field_name in field_names:
        credits.setdefault(field_name, [])
        credits[field_name] = unique([*credits[field_name], *values])


def split_credit_label(line: str) -> tuple[str, str]:
    match = re.match(r"^(.+?)[:：](.*)$", line)
    if not match:
        return "", ""
    return clean_text(match.group(1)), clean_text(match.group(2))


def credit_field_names(label: str) -> list[str]:
    normalized = re.sub(r"[（(].*?[）)]", "", label)
    if starts_parenthetical(normalized):
        return []
    field_names: list[str] = []
    for part in re.split(r"[・、,/／]", normalized):
        part = clean_text(part)
        field_name = CREDIT_LABELS.get(part)
        if field_name:
            field_names.append(field_name)
            continue
        for prefix, prefix_field_name in japanese_credit_prefixes().items():
            if part.startswith(prefix):
                field_names.append(prefix_field_name)
                break
    return unique(field_names)


def japanese_credit_prefixes() -> dict[str, str]:
    return {
        label: field_name
        for label, field_name in CREDIT_LABELS.items()
        if re.search(r"[ぁ-んァ-ン一-龯]", label)
    }


def standalone_credit_field_names(label: str) -> list[str]:
    field_names: list[str] = []
    for part in re.split(r"[・、,/／]", label):
        part = clean_text(part)
        field_name = CREDIT_LABELS.get(part)
        if field_name:
            field_names.append(field_name)
    return unique(field_names)


def is_credit_label_line(line: str) -> bool:
    label_text, _ = credit_label_and_value(line)
    return bool(label_text and credit_field_names(label_text))


def is_label_boundary_line(line: str) -> bool:
    label_text, value = split_credit_label(line)
    if label_text and not starts_parenthetical(label_text) and (credit_field_names(label_text) or not value):
        return True
    text = clean_text(line)
    if standalone_credit_field_names(text):
        return True
    return is_multiline_credit_label_start(line)


def split_credit_text(value: str) -> list[str]:
    parts: list[str] = []
    buffer = ""
    paren_depth = 0
    for char in value:
        if char in "（(":
            paren_depth += 1
            buffer += char
            continue
        if char in "）)" and paren_depth:
            paren_depth -= 1
            buffer += char
            continue
        if paren_depth == 0 and char in {"、", ",", "・", "/", "／"}:
            if buffer.strip():
                parts.append(buffer.strip())
            buffer = ""
            continue
        buffer += char
    if buffer.strip():
        parts.append(buffer.strip())
    return parts


def normalize_credit_values(values: list[str]) -> list[str]:
    result: list[str] = []
    note_buffer = ""
    for value in merge_credit_phrases(merge_unbalanced_parentheticals(values)):
        text = clean_text(value)
        if not text:
            continue
        if text in {"+", "＋"}:
            break
        if text.startswith("※"):
            break

        if note_buffer:
            note_buffer += text
            if closes_parenthetical(text):
                append_note_to_last_value(result, note_buffer)
                note_buffer = ""
            continue

        if is_parenthetical_note_fragment(text):
            if closes_parenthetical(text):
                append_note_to_last_value(result, text)
            else:
                note_buffer = text
            continue

        if is_parenthetical_note(text):
            if result:
                result[-1] = f"{result[-1]}{text}"
            continue
        if is_credit_value(text):
            result.append(remove_link_notes(text))
    if note_buffer:
        append_note_to_last_value(result, note_buffer)
    return unique(result)


def merge_credit_phrases(values: list[str]) -> list[str]:
    merged: list[str] = []
    index = 0
    while index < len(values):
        text = clean_text(values[index])
        if not text:
            index += 1
            continue

        if is_credit_connector(text) and merged and index + 1 < len(values):
            next_text = clean_text(values[index + 1])
            merged[-1] = clean_text(f"{merged[-1]} {text} {next_text}")
            index += 2
            continue

        if merged and should_join_credit_continuation(merged[-1], text):
            merged[-1] = clean_text(f"{merged[-1]} {text}")
            index += 1
            continue

        merged.append(text)
        index += 1
    return merged


def is_credit_connector(value: str) -> bool:
    return value in {"&", "＆"}


def should_join_credit_continuation(previous: str, current: str) -> bool:
    if not current:
        return False
    return bool(re.search(r"\bfeat\.?$|\bfeaturing$", previous, flags=re.I))


def merge_unbalanced_parentheticals(values: list[str]) -> list[str]:
    merged: list[str] = []
    buffer = ""
    for value in values:
        text = clean_text(value)
        if not text:
            continue
        buffer = f"{buffer}{text}" if buffer else text
        if parenthesis_balance(buffer) <= 0:
            merged.append(buffer)
            buffer = ""
    if buffer:
        merged.append(buffer)
    return merged


def parenthesis_balance(value: str) -> int:
    return sum(1 for char in value if char in "（(") - sum(
        1 for char in value if char in "）)"
    )


def is_parenthetical_note(value: str) -> bool:
    return bool(re.fullmatch(r"[（(].+?[）)]", value))


def is_parenthetical_note_fragment(value: str) -> bool:
    if not starts_parenthetical(value):
        return False
    return is_parenthetical_note(value) or parenthesis_balance(value) > 0


def starts_parenthetical(value: str) -> bool:
    return value.startswith(("（", "("))


def closes_parenthetical(value: str) -> bool:
    return value.endswith(("）", ")"))


def append_note_to_last_value(values: list[str], note: str) -> None:
    if values and not is_link_note(note):
        values[-1] = remove_link_notes(f"{values[-1]}{note}")


def is_link_note(value: str) -> bool:
    text = strip_parentheses(clean_text(value)).lower()
    if text in LINK_NOTE_LABELS:
        return True
    if text.endswith(("ホームページ", "公式サイト")):
        return True
    normalized = re.sub(r"[（）()\s・,/／]+", "", text)
    for token in COMPACT_LINK_NOTE_TOKENS:
        normalized = normalized.replace(token, "")
    return normalized == ""


def is_multiline_credit_label_start(line: str) -> bool:
    text = clean_text(line)
    if not text or split_credit_label(text)[0]:
        return False
    if parenthesis_balance(text) <= 0:
        return False
    return any(text.startswith(f"{label}（") or text.startswith(f"{label}(") for label in CREDIT_LABELS)


def remove_link_notes(value: str) -> str:
    result = value
    for pattern in (
        r"（[^（）()]+[）)]",
        r"\([^（）()]+[）)]",
    ):
        result = re.sub(
            pattern,
            lambda match: "" if is_link_note(match.group(0)) else match.group(0),
            result,
        )
    result = remove_dangling_link_note(result)
    result = re.sub(r"\s+([）)])", r"\1", result)
    return clean_text(result)


def remove_dangling_link_note(value: str) -> str:
    for opener in ("（", "("):
        index = value.rfind(opener)
        if index == -1:
            continue
        suffix = value[index + 1 :].strip()
        if not suffix or is_link_note(f"{opener}{suffix}{'）' if opener == '（' else ')'}"):
            return value[:index].strip()
    return value


def strip_parentheses(value: str) -> str:
    if is_parenthetical_note(value):
        return value[1:-1].strip()
    return value


def is_credit_value(value: str) -> bool:
    text = clean_text(value)
    if not text:
        return False
    if text in DISCARDED_CREDIT_VALUES:
        return False
    if text.endswith(" Remix"):
        return False
    if text.lower() in LINK_NOTE_LABELS:
        return False
    if text in {"）", "（"}:
        return False
    if re.fullmatch(r"[（）()]+", text):
        return False
    if re.fullmatch(r"[A-Z][a-z]+ \d{1,2}, \d{4}", text):
        return False
    return True


def extract_reading(soup: BeautifulSoup) -> str:
    heading = find_last_heading(soup, "曲紹介")
    if not heading:
        return ""
    for node in heading.find_next_siblings():
        if is_heading_node(node):
            break
        text = clean_text(node.get_text(""))
        if "曲名" in text:
            return extract_reading_from_text(text)
    return ""


def extract_reading_from_text(text: str) -> str:
    patterns = [
        r"曲名[:：]\s*『.+?』（(.+?)）",
        r"曲名[:：]\s*『.+?』\((.+?)\)",
        r"曲名[:：]\s*[^『』（）()]+（(.+?)）",
        r"曲名[:：]\s*[^『』（）()]+\((.+?)\)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return clean_text(match.group(1))
    return ""


def extract_introduction(soup: BeautifulSoup) -> list[str]:
    heading = find_last_heading(soup, "曲紹介")
    if heading:
        introduction = extract_section_items(heading)
        if introduction:
            return introduction[:8]

    lines = useful_lines(soup.get_text("\n"))
    start = find_last_line_index(lines, "曲紹介")
    if start is None:
        return []

    raw_lines: list[str] = []
    for line in lines[start + 1 :]:
        if line in SECTION_END_MARKERS:
            break
        if is_intro_fragment(line):
            raw_lines.append(line)
    return merge_intro_fragments(raw_lines)[:8]


def find_last_heading(soup: BeautifulSoup, text: str):
    headings = [
        node
        for node in soup.find_all(re.compile(r"^h[1-6]$"))
        if clean_text(node.get_text(" ")) == text
    ]
    return headings[-1] if headings else None


def extract_section_items(heading) -> list[str]:
    items: list[str] = []
    for node in heading.find_next_siblings():
        if is_heading_node(node):
            heading_text = clean_text(node.get_text(" "))
            if heading_text in SECTION_END_MARKERS or heading_text:
                break
        if getattr(node, "name", None) in {"ul", "ol"}:
            for item in node.find_all("li", recursive=False):
                add_intro_text(items, item.get_text(" "))
            continue
        if getattr(node, "name", None) in {"blockquote", "div", "p"}:
            add_intro_text(items, node.get_text(" "))
    return items


def is_heading_node(node) -> bool:
    return bool(getattr(node, "name", None) and re.fullmatch(r"h[1-6]", node.name))


def heading_level(node) -> int | None:
    if not is_heading_node(node):
        return None
    return int(node.name[1])


def add_intro_text(items: list[str], value: str) -> None:
    text = clean_intro_text(value)
    if is_intro_sentence(text) and text not in items:
        items.append(text)


def clean_intro_text(value: str) -> str:
    text = clean_text(value)
    if text.startswith("曲名："):
        return ""
    return text


def useful_lines(text: str) -> list[str]:
    return [clean_text(line) for line in text.splitlines() if clean_text(line)]


def find_last_line_index(lines: list[str], target: str) -> int | None:
    for index in range(len(lines) - 1, -1, -1):
        if lines[index] == target:
            return index
    return None


def find_credit_section_end(lines: list[str]) -> int | None:
    saw_credit = False
    for index, line in enumerate(lines):
        if is_credit_label_line(line):
            saw_credit = True
        elif saw_credit and line == "曲紹介":
            return index
    return None


def find_credit_section_start(lines: list[str], section_end: int) -> int:
    for index, line in enumerate(lines[:section_end]):
        if is_credit_label_line(line):
            return index
    return 0


def is_intro_fragment(line: str) -> bool:
    if not 1 <= len(line) <= 180:
        return False
    if len(line) <= 5 and line not in {"ミリオン"} and not re.search(r"\d", line):
        return False
    blocked_patterns = [
        r"^目次$",
        r"^作詞[:：]",
        r"^作曲[:：]",
        r"^編曲[:：]",
        r"^唄[:：]",
        r"^絵[:：]",
        r"^動画[:：]",
        r"^調声[:：]",
        r"^CPK! Remix$",
        r"^曲名[:：]",
        r"^こちら$",
        r"^』$",
        r"^曲紹介$",
        r"^歌詞$",
        r"^関連動画$",
        r"^コメント$",
    ]
    return not any(re.search(pattern, line) for pattern in blocked_patterns)


def merge_intro_fragments(lines: list[str]) -> list[str]:
    introduction: list[str] = []
    buffer = ""
    for line in lines:
        buffer = f"{buffer}{line}" if buffer else line
        if re.search(r"[。！？.!?]$", line):
            if is_intro_sentence(buffer) and buffer not in introduction:
                introduction.append(buffer)
            buffer = ""
    if buffer and is_intro_sentence(buffer) and buffer not in introduction:
        introduction.append(buffer)
    return introduction


def is_intro_sentence(value: str) -> bool:
    if not 6 <= len(value) <= 220:
        return False
    return not re.search(r"DLは。$", value)


def extract_videos(
    page_html: str,
    *,
    include_iframes: bool = True,
    include_links: bool = True,
) -> VideoMap:
    video_urls = video_source_urls(
        page_html,
        include_iframes=include_iframes,
        include_links=include_links,
    )
    niconico_ids = unique(
        video_id
        for url in video_urls
        for video_id in NICONICO_ID_PATTERN.findall(url)
    )
    youtube_ids = unique(
        video_id
        for url in video_urls
        for video_id in YOUTUBE_ID_PATTERN.findall(url)
    )
    return {
        "niconico": video_entries(
            niconico_ids,
            niconico_video_entry,
        ),
        "youtube": video_entries(
            youtube_ids,
            youtube_video_entry,
        ),
    }


def video_entries(
    video_ids: list[str],
    entry_factory,
) -> list[dict[str, str]]:
    if len(video_ids) <= 1:
        return [entry_factory(video_id) for video_id in video_ids]
    with ThreadPoolExecutor(max_workers=min(6, len(video_ids))) as executor:
        return list(executor.map(entry_factory, video_ids))


def video_source_urls(
    page_html: str,
    *,
    include_iframes: bool,
    include_links: bool,
) -> list[str]:
    urls: list[str] = []
    if include_iframes:
        urls.extend(unescape(url) for url in IFRAME_SRC_PATTERN.findall(page_html))
    if include_links:
        urls.extend(unescape(url) for url in LINK_HREF_PATTERN.findall(page_html))
    return urls


def merge_video_maps(*video_maps: VideoMap) -> VideoMap:
    return {
        "niconico": unique_video_entries(
            [video for video_map in video_maps for video in video_map["niconico"]]
        ),
        "youtube": unique_video_entries(
            [video for video_map in video_maps for video in video_map["youtube"]]
        ),
    }


def unique_video_entries(videos: list[dict[str, str]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for video in videos:
        video_id = video.get("id", "")
        if video_id and video_id not in seen:
            seen.add(video_id)
            result.append(video)
    return result


def split_video_sections(page_html: str) -> tuple[str, str]:
    soup = clean_soup(page_html, remove_media=False)
    related_heading = find_last_heading(soup, "関連動画")
    if not related_heading:
        return page_html, ""

    related_level = heading_level(related_heading) or 6
    related_nodes = []
    for node in list(related_heading.find_next_siblings()):
        node_level = heading_level(node)
        if node_level is not None and node_level <= related_level:
            break
        related_nodes.append(str(node))
        node.decompose()
    related_heading.decompose()
    return str(soup), "".join(related_nodes)


def remove_excluded_video_sections(page_html: str) -> str:
    if not any(heading in page_html for heading in EXCLUDED_VIDEO_SECTION_HEADINGS):
        return page_html
    soup = clean_soup(page_html, remove_media=False)
    for heading in find_headings(soup, EXCLUDED_VIDEO_SECTION_HEADINGS):
        remove_heading_section(heading)
    return str(soup)


def find_headings(soup: BeautifulSoup, texts: set[str]) -> list:
    return [
        node
        for node in soup.find_all(re.compile(r"^h[1-6]$"))
        if clean_text(node.get_text(" ")) in texts
    ]


def remove_heading_section(heading) -> None:
    section_level = heading_level(heading) or 6
    for node in list(heading.find_next_siblings()):
        node_level = heading_level(node)
        if node_level is not None and node_level <= section_level:
            break
        node.decompose()
    heading.decompose()


def niconico_video_entry(
    video_id: str,
) -> dict[str, str]:
    thumbnail_urls = fallback_niconico_thumbnail_urls(video_id)
    return {
        "id": video_id,
        "url": f"https://www.nicovideo.jp/watch/{video_id}",
        "title": f"ニコニコ動画 {video_id}",
        "thumbnail_url": thumbnail_urls[0],
        "thumbnail_urls": thumbnail_urls,
    }


def youtube_video_entry(video_id: str) -> dict[str, str]:
    quoted_id = urllib.parse.quote(video_id)
    thumbnail_urls = fallback_youtube_thumbnail_urls(video_id)
    return {
        "id": video_id,
        "url": f"https://www.youtube.com/watch?v={quoted_id}",
        "title": f"YouTube {video_id}",
        "thumbnail_url": thumbnail_urls[0],
        "thumbnail_urls": thumbnail_urls,
    }


def fallback_niconico_thumbnail_url(video_id: str) -> str:
    return fallback_niconico_thumbnail_urls(video_id)[0]


def fallback_niconico_thumbnail_urls(video_id: str) -> list[str]:
    numeric_id = re.sub(r"^[a-z]+", "", video_id, flags=re.I)
    base_url = f"https://nicovideo.cdn.nimg.jp/thumbnails/{numeric_id}/{numeric_id}"
    return [
        f"{base_url}.L",
        f"{base_url}.M",
        base_url,
    ]


def fallback_youtube_thumbnail_urls(video_id: str) -> list[str]:
    quoted_id = urllib.parse.quote(video_id)
    base_url = f"https://img.youtube.com/vi/{quoted_id}"
    return [
        f"{base_url}/maxresdefault.jpg",
        f"{base_url}/hqdefault.jpg",
        f"{base_url}/mqdefault.jpg",
        f"{base_url}/default.jpg",
    ]


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result
