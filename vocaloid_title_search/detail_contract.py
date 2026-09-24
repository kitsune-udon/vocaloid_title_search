"""Validate stored details at the publication boundary, without repairing source data."""
from urllib.parse import urlsplit
from vocaloid_title_search.detail import is_allowed_wiki_url

CREDIT_KEYS = {"lyricist", "composer", "arranger", "vocalist", "illustrator", "video", "tuning"}


def string_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def web_url(value: object, *, empty: bool = False) -> bool:
    if empty and value == "":
        return True
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.hostname) and not parsed.username
    except ValueError:
        return False


def valid_detail(detail: dict, url: str, *, complete: bool) -> bool:
    required = {"page_title", "reading", "published_year", "credits", "introduction", "videos", "related_videos", "source_url"}
    if complete and not required.issubset(detail):
        return False
    for key in ("page_title", "reading", "source_url"):
        if key in detail and not isinstance(detail[key], str):
            return False
    if complete and (not detail["page_title"].strip() or detail["source_url"] != url
                     or not is_allowed_wiki_url(url)):
        return False
    year = detail.get("published_year")
    if year is not None and (type(year) is not int or not 0 <= year <= 9999):
        return False
    if "introduction" in detail and not string_list(detail["introduction"]):
        return False
    if "credits" in detail:
        credits = detail["credits"]
        if not isinstance(credits, dict) or any(key not in CREDIT_KEYS or not string_list(value) for key, value in credits.items()):
            return False
    for key in ("videos", "related_videos"):
        if key not in detail:
            continue
        section = detail[key]
        # Legacy local reports can count a flat video list; public API requires a map.
        if isinstance(section, list) and not complete:
            continue
        if not isinstance(section, dict):
            return False
        if complete and not {"niconico", "youtube"}.issubset(section):
            return False
        if any(service not in {"niconico", "youtube"} for service in section):
            return False
        for entries in section.values():
            if not isinstance(entries, list):
                return False
            for video in entries:
                if not isinstance(video, dict):
                    return False
                fields = {"id", "url", "title", "thumbnail_url"}
                if complete and not fields.issubset(video):
                    return False
                if any(key in video and not isinstance(video[key], str) for key in fields):
                    return False
                if complete and (not video["id"] or not web_url(video["url"]) or not web_url(video["thumbnail_url"], empty=True)):
                    return False
                if "thumbnail_urls" in video and (not string_list(video["thumbnail_urls"]) or not all(web_url(item) for item in video["thumbnail_urls"])):
                    return False
    return True
