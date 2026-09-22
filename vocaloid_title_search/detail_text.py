"""HTML and text primitives shared by detail extractors."""
import re
from bs4 import BeautifulSoup


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


def find_last_heading(soup: BeautifulSoup, text: str):
    headings = [
        node
        for node in soup.find_all(re.compile(r"^h[1-6]$"))
        if clean_text(node.get_text(" ")) == text
    ]
    return headings[-1] if headings else None


def is_heading_node(node) -> bool:
    return bool(getattr(node, "name", None) and re.fullmatch(r"h[1-6]", node.name))


def heading_level(node) -> int | None:
    if not is_heading_node(node):
        return None
    return int(node.name[1])


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result
