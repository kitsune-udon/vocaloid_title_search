"""Structured detail extraction from Hatsune Miku Wiki song pages."""

import re
import urllib.parse
from dataclasses import asdict, dataclass, field

from bs4 import BeautifulSoup, Comment, NavigableString

from vocaloid_title_search.detail_text import (
    clean_soup,
    clean_text,
    find_last_heading,
    heading_level,
    is_heading_node,
    remove_noise_nodes,
    unique,
)
from vocaloid_title_search.detail_videos import (
    extract_videos,
    fallback_niconico_thumbnail_url,
    fallback_niconico_thumbnail_urls,
    fallback_youtube_thumbnail_urls,
    find_headings,
    merge_video_maps,
    niconico_video_entry,
    remove_excluded_video_sections,
    remove_heading_section,
    split_video_sections,
    unique_video_entries,
    video_entries,
    video_source_urls,
    youtube_video_entry,
)

from vocaloid_title_search.http import fetch_text as http_fetch_text


USER_AGENT = "vocaloid-title-search/1.0"
CREDIT_LABELS = {
    "作詞": "lyricist",
    "作曲": "composer",
    "編曲": "arranger",
    "唄": "vocalist",
    "歌": "vocalist",
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
# Unlinked names whose punctuation is ambiguous. Values identify the independently
# reviewed wiki page with a single matching name link; do not infer from spelling.
COMPOUND_CREDIT_NAMES = {"タケ・ヨシキ": "3581"}
INTRODUCTION_HEADINGS = ("曲紹介", "概要", "曲の内容")
SECTION_END_MARKERS = {"歌詞", "関連動画", "コメント"}
SUBSECTION_MARKER_LINE = "+"
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
    "個人サイト",
    "公式hp",
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
    "個人サイト",
    "公式hp",
    "site",
    "hp",
    "fanbox",
    "skeb",
    "x",
)


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
    protected_names: dict[str, str] = {}
    section_groups: set[str] = set()
    lines = credit_section_lines(soup, protected_names=protected_names, section_groups=section_groups)
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
            if line in SECTION_END_MARKERS or line in INTRODUCTION_HEADINGS or line in section_groups:
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
    for field_name, values in credits.items():
        restored = []
        for value in values:
            for token, name in protected_names.items():
                value = value.replace(token, name)
            restored.append(remove_link_notes(value))
        credits[field_name] = unique(restored)
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
    return bool(re.search(r"^Re:|(?:Remix|RMX|Reloaded|ver\.|版|edit)$", text, flags=re.I))


def credit_label_and_value(line: str) -> tuple[str, str]:
    label_text, value = split_credit_label(line)
    if label_text:
        return label_text, value
    text = clean_text(line)
    natural_label = re.match(r"^(.+?)を\s+(.+)$", text)
    if natural_label and credit_field_names(natural_label.group(1)):
        return natural_label.group(1), natural_label.group(2)
    if standalone_credit_field_names(text):
        return text, ""
    return "", ""


def credit_section_lines(
    soup: BeautifulSoup, *, protected_names: dict[str, str] | None = None,
    section_groups: set[str] | None = None,
) -> list[str]:
    # HTML links and emphasis are inline, not person or row boundaries. Keep
    # structural breaks while protecting punctuation inside a linked name.
    prefix = "\ue000credit"
    text = soup.get_text()
    while prefix in text:
        prefix += "_"
    blocks = {"div", "p", "li", "ul", "ol", "table", "tr", "td", "th", "section",
              "article", "blockquote", "nav", "header", "footer", "h1", "h2", "h3",
              "h4", "h5", "h6", "dt", "dd", "summary"}

    def render(node):
        if isinstance(node, Comment):
            return ""
        if isinstance(node, NavigableString):
            value = str(node)
            if protected_names is not None:
                for name in COMPOUND_CREDIT_NAMES:
                    if name in value:
                        token = f"{prefix}{len(protected_names)}\ue001"
                        protected_names[token] = name
                        value = value.replace(name, token)
            return value
        if node.name == "br":
            return "\n"
        if node.name == "a":
            name = clean_text(node.get_text(""))
            if (protected_names is not None and any(char in name for char in "、,・/／､･：:")
                    and not is_credit_label_line(name) and not standalone_credit_field_names(name)):
                token = f"{prefix}{len(protected_names)}\ue001"
                protected_names[token] = name
                return token
            return name
        rendered = "".join(render(child) for child in node.children)
        if node.name in {"div", "p"}:
            first = next((child for child in node.children if not isinstance(child, Comment)
                          and clean_text(str(child) if isinstance(child, NavigableString) else child.get_text())), None)
            lead = clean_text(str(first) if isinstance(first, NavigableString) else first.get_text() if first else "")
            version_group = is_parenthetical_note(lead) and is_alternate_version_heading(strip_parentheses(lead))
            staff_heading = (re.fullmatch(r"(?:動画|映像|イラスト)担当", clean_text(node.get_text()))
                             and node.find_parent("table", class_="atwiki_plugin_region") is not None)
            if version_group or staff_heading:
                marker = f"{prefix}group"
                if section_groups is not None:
                    section_groups.add(marker)
                rendered = f"{marker}\n{rendered}"
        if is_heading_node(node):
            return f"\n{prefix}heading\n{rendered}\n"
        return f"\n{rendered}\n" if node.name in blocks else rendered

    lines = useful_lines(split_inline_credit_roles(render(soup)))
    section_end = find_credit_section_end(lines, structural_end=f"{prefix}heading")
    if section_end is None:
        section_end = len(lines)
    section_start = find_credit_section_start(lines, section_end)
    return lines[section_start:section_end]



def split_inline_credit_roles(text: str) -> str:
    result = []
    depth = 0
    for index, char in enumerate(text):
        if char in "（(":
            depth += 1
        elif char in "）)" and depth:
            depth -= 1
        if char == "　" and depth == 0 and re.match(r"[^\s：:]+：", text[index + 1:]):
            result.append("\n")
        else:
            result.append(char)
    return "".join(result)


def add_credit_values(
    credits: dict[str, list[str]],
    field_names: list[str],
    values: list[str],
) -> None:
    for field_name in field_names:
        credits.setdefault(field_name, [])
        credits[field_name] = unique([*credits[field_name], *values])


def split_credit_label(line: str) -> tuple[str, str]:
    depth = 0
    for index, char in enumerate(line):
        if char in "（(":
            depth += 1
        elif char in "）)" and depth:
            depth -= 1
        elif char in ":：" and depth == 0 and index:
            return clean_text(line[:index]), clean_text(line[index + 1:])
    return "", ""


def credit_field_names(label: str) -> list[str]:
    if any(is_alternate_version_heading(note) for note in re.findall(r"[（(]([^（）()]+)[）)]", label)):
        return []
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
        if label != "歌" and re.search(r"[ぁ-んァ-ン一-龯]", label)
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
    label_text, value = credit_label_and_value(line)
    if label_text and not starts_parenthetical(label_text) and (
        credit_field_names(label_text) or not value or "：" in line or re.search(r"\s:|:\s", line)
    ):
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
        if paren_depth == 0 and char in {"、", ",", "・", "/", "／", "､", "･"}:
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
    heading = next((heading for text in INTRODUCTION_HEADINGS if (heading := find_last_heading(soup, text))), None)
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
    heading = next((heading for text in INTRODUCTION_HEADINGS if (heading := find_last_heading(soup, text))), None)
    if heading:
        introduction = extract_section_items(heading)
        if introduction:
            return introduction[:8]

    lines = useful_lines(soup.get_text("\n"))
    start = next((index for text in INTRODUCTION_HEADINGS if (index := find_last_line_index(lines, text)) is not None), None)
    if start is None:
        return []

    raw_lines: list[str] = []
    for line in lines[start + 1 :]:
        if line in SECTION_END_MARKERS:
            break
        if is_intro_fragment(line):
            raw_lines.append(line)
    return merge_intro_fragments(raw_lines)[:8]


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


def add_intro_text(items: list[str], value: str) -> None:
    text = clean_intro_text(value)
    if text and text not in SECTION_END_MARKERS and is_intro_sentence(text, minimum_length=1) and text not in items:
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


def find_credit_section_end(lines: list[str], *, structural_end: str | None = None) -> int | None:
    saw_credit = False
    for index, line in enumerate(lines):
        if is_credit_label_line(line):
            saw_credit = True
        elif saw_credit and (line == structural_end or line in INTRODUCTION_HEADINGS or line in SECTION_END_MARKERS):
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


def is_intro_sentence(value: str, *, minimum_length: int = 6) -> bool:
    if not minimum_length <= len(value) <= 220:
        return False
    return not re.search(r"DLは。$", value)
