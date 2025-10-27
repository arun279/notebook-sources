from __future__ import annotations

import pytest
import requests
import responses

from backend.core.wikipedia_parser import WikipediaParser


@responses.activate
def test_fetch_html_success():
    """Verify that fetch_html returns content on a successful request."""
    url = "https://example.com"
    responses.add(responses.GET, url, body="<html></html>", status=200)
    parser = WikipediaParser()
    html = parser.fetch_html(url)
    assert html == "<html></html>"


@responses.activate
def test_fetch_html_error():
    """Verify that fetch_html raises an exception on a failed request."""
    url = "https://example.com"
    responses.add(responses.GET, url, status=404)
    parser = WikipediaParser()
    with pytest.raises(requests.HTTPError):
        parser.fetch_html(url)
