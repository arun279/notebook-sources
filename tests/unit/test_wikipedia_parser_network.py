from __future__ import annotations

import pytest
import requests

from backend.core.wikipedia_parser import WikipediaParser


def test_fetch_html_success(requests_mock):
    """Verify that fetch_html returns content on a successful request."""
    url = "https://example.com"
    requests_mock.get(url, text="<html></html>")
    parser = WikipediaParser()
    html = parser.fetch_html(url)
    assert html == "<html></html>"


def test_fetch_html_error(requests_mock):
    """Verify that fetch_html raises an exception on a failed request."""
    url = "https://example.com"
    requests_mock.get(url, status_code=404)
    parser = WikipediaParser()
    with pytest.raises(requests.HTTPError):
        parser.fetch_html(url)
