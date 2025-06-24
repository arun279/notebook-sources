from __future__ import annotations

import responses
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