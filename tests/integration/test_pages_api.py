from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from backend.main import app
from backend.api import routes_pages
from backend.core import models
from backend.infra.repositories.memory_repo import InMemoryRepository


def test_references_by_page(monkeypatch):
    print("Executing test_references_by_page")
    # Swap repository to in-memory for test isolation
    repo = InMemoryRepository()
    monkeypatch.setattr(routes_pages, "repo", repo, raising=True)

    # Create a page and references
    page = repo.create_wikipedia_page(url="https://en.wikipedia.org/wiki/Test_Page", title="Test Page Title")
    refs = [
        models.Reference(url="https://a.com", title="A"),
        models.Reference(url="https://b.com", title="B"),
    ]
    repo.add_references(page, refs)

    client = TestClient(app)

    # Retrieve reference list by page
    resp = client.get(f"/api/v1/pages/{page.id}/references")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["references"]) == 2
    assert data["title"] == "Test Page Title"
