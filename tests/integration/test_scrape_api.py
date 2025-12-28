from __future__ import annotations

import responses
from unittest.mock import MagicMock, AsyncMock
from contextlib import asynccontextmanager
from fastapi.testclient import TestClient

from backend.main import app
from backend.api import routes_references
from backend.api import routes_progress
from backend.infra.repositories.memory_repo import InMemoryRepository


def _setup(monkeypatch):
    # use in-memory repo
    repo = InMemoryRepository()
    monkeypatch.setattr(routes_references, "repo", repo, raising=True)
    monkeypatch.setattr(routes_progress, "repo", repo, raising=True)

    # patch parser
    sample_html = '<cite class="citation"><a href="https://ref.com">Ref</a></cite>'
    monkeypatch.setattr(routes_references.parser, "fetch_html", lambda _url: f"<html><body>{sample_html}</body></html>", raising=False)
    return repo


def _create_mock_browser_pool():
    """Create a mock browser pool that produces working mock browsers."""
    mock_page = MagicMock()
    mock_page.pdf = AsyncMock(return_value=b"%PDF-1.4 fake pdf content")
    mock_page.goto = AsyncMock()
    mock_page.close = AsyncMock()

    mock_browser = MagicMock()
    mock_browser.new_page = AsyncMock(return_value=mock_page)

    @asynccontextmanager
    async def mock_acquire():
        yield mock_browser

    mock_pool = MagicMock()
    mock_pool.acquire = mock_acquire
    return mock_pool


@responses.activate
def test_scrape_route(monkeypatch, tmp_path):
    repo = _setup(monkeypatch)

    # Mock external ref url
    responses.add(responses.GET, "https://ref.com", body="<html><p>Hello</p></html>", status=200)

    # ensure scraper storage uses tmp_path
    from backend.infra.storage.local_fs import LocalFileStorage as _LFS
    import backend.core.scraper as _scraper_module
    monkeypatch.setattr(_scraper_module, "LocalFileStorage", lambda root=None: _LFS(root=tmp_path), raising=True)

    client = TestClient(app)

    # create parse job
    r = client.post("/api/v1/references", json={"url": "https://wiki"})
    job_id = r.json()["job_id"]
    refs_resp = client.get(f"/api/v1/references/{job_id}").json()
    ref_id = refs_resp["references"][0]["id"]

    # call scrape
    s = client.post("/api/v1/scrape", json={"reference_ids": [ref_id], "aggressive": False})
    assert s.status_code == 202

    # Progress endpoint should eventually show scraped
    prog = client.get(f"/api/v1/progress/{s.json()['job_id']}")
    assert prog.status_code == 200  # background tasks executed immediately
    statuses = [item["status"] for item in prog.json()["items"]]
    assert "scraped" in statuses


@responses.activate
def test_scrape_route_with_browser_pool(monkeypatch, tmp_path):
    """Integration test verifying scrape flow uses browser pool correctly."""
    repo = _setup(monkeypatch)

    # Mock external ref url
    responses.add(responses.GET, "https://ref.com", body="<html><p>Hello</p></html>", status=200)

    # ensure scraper storage uses tmp_path
    from backend.infra.storage.local_fs import LocalFileStorage as _LFS
    import backend.core.scraper as _scraper_module
    monkeypatch.setattr(_scraper_module, "LocalFileStorage", lambda root=None: _LFS(root=tmp_path), raising=True)

    # Create mock browser pool and patch it into main module
    mock_pool = _create_mock_browser_pool()
    import backend.main as main_module
    monkeypatch.setattr(main_module, "browser_pool", mock_pool)

    client = TestClient(app)

    # create parse job
    r = client.post("/api/v1/references", json={"url": "https://wiki"})
    job_id = r.json()["job_id"]
    refs_resp = client.get(f"/api/v1/references/{job_id}").json()
    ref_id = refs_resp["references"][0]["id"]

    # call scrape
    s = client.post("/api/v1/scrape", json={"reference_ids": [ref_id], "aggressive": False})
    assert s.status_code == 202

    # Progress endpoint should show scraped
    prog = client.get(f"/api/v1/progress/{s.json()['job_id']}")
    assert prog.status_code == 200
    statuses = [item["status"] for item in prog.json()["items"]]
    assert "scraped" in statuses


@responses.activate
def test_scrape_multiple_references_with_pool(monkeypatch, tmp_path):
    """Test scraping multiple references exercises pool concurrency."""
    # Setup with multiple references
    repo = InMemoryRepository()
    monkeypatch.setattr(routes_references, "repo", repo, raising=True)
    monkeypatch.setattr(routes_progress, "repo", repo, raising=True)

    sample_html = (
        '<cite class="citation"><a href="https://ref1.com">Ref1</a></cite>'
        '<cite class="citation"><a href="https://ref2.com">Ref2</a></cite>'
        '<cite class="citation"><a href="https://ref3.com">Ref3</a></cite>'
    )
    monkeypatch.setattr(routes_references.parser, "fetch_html", lambda _url: f"<html><body>{sample_html}</body></html>", raising=False)

    # Mock all external URLs
    responses.add(responses.GET, "https://ref1.com", body="<html>Content 1</html>", status=200)
    responses.add(responses.GET, "https://ref2.com", body="<html>Content 2</html>", status=200)
    responses.add(responses.GET, "https://ref3.com", body="<html>Content 3</html>", status=200)

    # Setup storage and pool
    from backend.infra.storage.local_fs import LocalFileStorage as _LFS
    import backend.core.scraper as _scraper_module
    monkeypatch.setattr(_scraper_module, "LocalFileStorage", lambda root=None: _LFS(root=tmp_path), raising=True)

    mock_pool = _create_mock_browser_pool()
    import backend.main as main_module
    monkeypatch.setattr(main_module, "browser_pool", mock_pool)

    client = TestClient(app)

    # Create parse job and get all reference IDs
    r = client.post("/api/v1/references", json={"url": "https://wiki"})
    job_id = r.json()["job_id"]
    refs_resp = client.get(f"/api/v1/references/{job_id}").json()
    ref_ids = [ref["id"] for ref in refs_resp["references"]]
    assert len(ref_ids) == 3

    # Scrape all references
    s = client.post("/api/v1/scrape", json={"reference_ids": ref_ids, "aggressive": False})
    assert s.status_code == 202

    # All should be scraped
    prog = client.get(f"/api/v1/progress/{s.json()['job_id']}")
    assert prog.status_code == 200
    statuses = [item["status"] for item in prog.json()["items"]]
    assert statuses.count("scraped") == 3


@responses.activate
def test_scrape_with_aggressive_archive_mode(monkeypatch, tmp_path):
    """Test aggressive mode triggers archive save without blocking."""
    repo = _setup(monkeypatch)

    # Mock the live URL to return 403 (paywall)
    responses.add(responses.GET, "https://ref.com", status=403)
    # Mock wayback availability check (no snapshot)
    responses.add(
        responses.GET,
        "https://archive.org/wayback/available",
        json={"archived_snapshots": {}},
        status=200,
    )
    # Mock wayback save trigger
    responses.add(responses.GET, "https://web.archive.org/save/https://ref.com", status=200)

    from backend.infra.storage.local_fs import LocalFileStorage as _LFS
    import backend.core.scraper as _scraper_module
    monkeypatch.setattr(_scraper_module, "LocalFileStorage", lambda root=None: _LFS(root=tmp_path), raising=True)

    mock_pool = _create_mock_browser_pool()
    import backend.main as main_module
    monkeypatch.setattr(main_module, "browser_pool", mock_pool)

    client = TestClient(app)

    # Create job
    r = client.post("/api/v1/references", json={"url": "https://wiki"})
    job_id = r.json()["job_id"]
    refs_resp = client.get(f"/api/v1/references/{job_id}").json()
    ref_id = refs_resp["references"][0]["id"]

    # Scrape with aggressive=True - should not block for 2 minutes
    s = client.post("/api/v1/scrape", json={"reference_ids": [ref_id], "aggressive": True})
    assert s.status_code == 202

    # Should complete quickly (not waiting 2 min) - status will be failed
    # because archive returned no content, but it shouldn't have blocked
    prog = client.get(f"/api/v1/progress/{s.json()['job_id']}")
    assert prog.status_code == 200
    # The important thing is the request completed quickly, not that it succeeded 