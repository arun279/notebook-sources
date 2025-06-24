from __future__ import annotations

import responses
from fastapi.testclient import TestClient

from backend.main import app
from backend.api import routes_references, routes_progress
from backend.infra.repositories.memory_repo import InMemoryRepository


def _setup(monkeypatch, tmp_path):
    # use in-memory repo and tmp storage
    repo = InMemoryRepository()
    monkeypatch.setattr(routes_references, "repo", repo, raising=True)
    monkeypatch.setattr(routes_progress, "repo", repo, raising=True)

    # patch storage root
    from backend.infra.storage.local_fs import LocalFileStorage as _LFS
    import backend.core.scraper as _scraper_module
    monkeypatch.setattr(_scraper_module, "LocalFileStorage", lambda root=None: _LFS(root=tmp_path), raising=True)

    # patch parser minimal
    sample_html = '<cite class="citation"><a href="https://ref.com">Ref</a></cite>'
    monkeypatch.setattr(routes_references.parser, "fetch_html", lambda _url: f"<html><body>{sample_html}</body></html>", raising=False)

    monkeypatch.setattr(routes_progress, "storage", _LFS(tmp_path), raising=True)

    return repo


@responses.activate
def test_download_single_pdf(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    responses.add(responses.GET, "https://ref.com", body="<html>Hello</html>", status=200)

    client = TestClient(app)
    job_id = client.post("/api/v1/references", json={"url": "https://wiki"}).json()["job_id"]
    ref_id = client.get(f"/api/v1/references/{job_id}").json()["references"][0]["id"]
    scrape_job = client.post("/api/v1/scrape", json={"reference_ids": [ref_id]}).json()["job_id"]

    # download single
    download_resp = client.get("/api/v1/download", params={"ids": ref_id})
    assert download_resp.status_code == 200
    assert download_resp.headers["content-type"] == "application/pdf"


@responses.activate
def test_download_zip(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    responses.add(responses.GET, "https://ref.com", body="<html>Hello</html>", status=200)

    client = TestClient(app)
    job_id = client.post("/api/v1/references", json={"url": "https://wiki"}).json()["job_id"]
    ref_id = client.get(f"/api/v1/references/{job_id}").json()["references"][0]["id"]
    _ = client.post("/api/v1/scrape", json={"reference_ids": [ref_id]})

    # download all
    download_resp = client.get("/api/v1/download", params={"all": "true"})
    assert download_resp.status_code == 200
    assert download_resp.headers["content-type"] == "application/zip" 