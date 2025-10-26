from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app
from backend.api import routes_references
from backend.infra.repositories.memory_repo import InMemoryRepository


def test_references_round_trip(monkeypatch):
    # Swap repository to in-memory for test isolation
    repo = InMemoryRepository()
    monkeypatch.setattr(routes_references, "repo", repo, raising=True)

    # Patch WikipediaParser.fetch_html to produce deterministic HTML with 2 cites
    sample_html = (
        '<cite class="citation"><a href="https://a.com">A</a></cite>'
        '<cite class="citation"><a href="https://b.com">B</a></cite>'
    )
    monkeypatch.setattr(routes_references.parser, "fetch_html", lambda _url: f"<html><body>{sample_html}</body></html>", raising=False)

    client = TestClient(app)

    # 1. Post references parse job
    resp = client.post("/api/v1/references", json={"url": "https://en.wikipedia.org/wiki/Dummy"})
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]

    # 2. Retrieve reference list
    resp2 = client.get(f"/api/v1/references/{job_id}")
    assert resp2.status_code == 200
    data = resp2.json()
    assert len(data["references"]) == 2 