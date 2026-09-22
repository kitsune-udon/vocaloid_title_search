"""Video links, sections, and thumbnail candidates; no network requests."""
import re
import urllib.parse
from html import unescape
from bs4 import BeautifulSoup
from vocaloid_title_search.detail_text import clean_soup, clean_text, find_last_heading, heading_level, unique


EXCLUDED_VIDEO_SECTION_HEADINGS = {"英語版"}


NICONICO_ID_PATTERN = re.compile(
    r"(?:nicovideo\.jp/watch/|ext\.nicovideo\.jp/thumb/)((?:sm|nm|so)\d+)"
)


YOUTUBE_ID_PATTERN = re.compile(
    r"(?:youtube\.com/(?:watch\?v=|embed/)|youtu\.be/)([A-Za-z0-9_-]{11})"
)


IFRAME_SRC_PATTERN = re.compile(r"<iframe\b[^>]*\bsrc=[\"']([^\"']+)[\"']", re.I)


LINK_HREF_PATTERN = re.compile(r"<a\b[^>]*\bhref=[\"']([^\"']+)[\"']", re.I)


VideoMap = dict[str, list[dict[str, str]]]


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
    return [entry_factory(video_id) for video_id in video_ids]


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
