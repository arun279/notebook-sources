from __future__ import annotations

import responses

from backend.core import models
from backend.core.scraper import Scraper


@responses.activate
def test_scraper_happy_path(tmp_path):
    test_url = "https://example.com/article"
    html_body = "<html><body><p>Hello</p></body></html>"
    responses.add(responses.GET, test_url, body=html_body, status=200)

    ref = models.Reference(url=test_url)
    scraper = Scraper(job_id="unit-test")
    # Override storage root to tmp_path for isolation
    scraper._storage.root = tmp_path  # type: ignore[attr-defined,assignment]

    success, error = scraper.scrape(ref)
    assert success
    assert error is None

    # Files should exist
    assert (tmp_path / ref.html_path).exists()
    assert (tmp_path / ref.pdf_path).exists()
    assert ref.status == models.ReferenceStatus.scraped 

def test_scraper_paywalled(monkeypatch, tmp_path):
    test_url = "https://paywall.com/article"
    ref = models.Reference(url=test_url, suspected_paywall=True)

    # Patch ArchiveResolver to return success
    class DummyOutcome:
        success = True
        html = "<html><p>Archive</p></html>"
        archive_url = "https://archive.org/abc"

    monkeypatch.setattr("backend.core.scraper.ArchiveResolver", lambda: type("X", (), {"resolve": lambda self, url, paywalled, aggressive: DummyOutcome})(), raising=True)

    scraper = Scraper(job_id="pw-test")
    scraper._storage.root = tmp_path  # type: ignore

    success, _ = scraper.scrape(ref)
    assert success
    assert ref.archive_source == DummyOutcome.archive_url
    assert ref.status == models.ReferenceStatus.scraped 

@responses.activate
def test_scraper_http_error(monkeypatch, tmp_path):
    url = "https://fail.com"
    responses.add(responses.GET, url, status=404)

    ref = models.Reference(url=url)
    scraper = Scraper(job_id="err")
    scraper._storage.root = tmp_path  # type: ignore

    success, err = scraper.scrape(ref)
    assert not success
    assert err is not None
    assert ref.status == models.ReferenceStatus.failed 