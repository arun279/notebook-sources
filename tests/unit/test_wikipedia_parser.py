from __future__ import annotations

import re
from typing import List

import pytest
from hypothesis import given, strategies as st
from hypothesis import settings, HealthCheck

from backend.core.wikipedia_parser import WikipediaParser


@st.composite
def citation_html(draw):
    """Strategy generating a single <cite> block with link."""
    url = draw(st.from_regex(r"https?://[\w\.-]+", fullmatch=True))
    title_text = draw(st.text(min_size=1, max_size=20))
    html = f'<cite class="citation"><a href="{url}">{title_text}</a></cite>'
    return url, html


@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=50)
@given(st.lists(citation_html(), min_size=0, max_size=5))
def test_parser_outputs_at_most_citations(items: List[tuple[str, str]]):
    parser = WikipediaParser()

    urls, cites = zip(*items) if items else ([], [])
    full_html = "<html><body>" + "".join(cites) + "</body></html>"

    # Patch fetch_html to return our generated HTML
    parser.fetch_html = lambda _url: full_html  # type: ignore[assignment]

    results = parser.parse("https://dummy")
    assert len(results) <= len(cites)
    # Confirm URLs are preserved
    for ref in results:
        assert any(ref.url == u for u in urls)


@pytest.mark.parametrize("count", [0, 1, 3])
def test_parser_basic(count):
    cites = [
        f'<cite class="citation"><a href="https://example.com/{i}">Link {i}</a></cite>'
        for i in range(count)
    ]
    html = "<html><body>" + "".join(cites) + "</body></html>"
    parser = WikipediaParser()
    parser.fetch_html = lambda _url: html  # type: ignore
    refs = parser.parse("https://dummy")
    assert len(refs) == count 