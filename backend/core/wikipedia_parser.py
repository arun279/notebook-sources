from __future__ import annotations

from typing import List

import requests
from bs4 import BeautifulSoup
import mwparserfromhell as mwp  # type: ignore

from backend.core import models


class WikipediaParser:
    """Parses a Wikipedia article and extracts references.

    Note: This is a **very** naive implementation that should be refined.
    """

    WIKI_MOBILE = "https://en.wikipedia.org/api/rest_v1/page/mobile-html/{}"

    def __init__(self) -> None:
        self.last_title: str | None = None

    def fetch_html(self, url: str) -> str:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, url: str) -> List[models.Reference]:
        html = self.fetch_html(url)
        soup = BeautifulSoup(html, "html.parser")
        title_tag = soup.find("title")
        self.last_title = title_tag.get_text(strip=True) if title_tag else None

        # Very naive extraction: find all <cite class="citation"> then get the <a> inside.
        references: list[models.Reference] = []
        for cite in soup.select("cite.citation"):
            link = cite.find("a", href=True)
            if not link:
                continue
            ref = models.Reference(
                url=link["href"],
                title=link.get_text(strip=True) or link["href"],
            )
            references.append(ref)

        return references 