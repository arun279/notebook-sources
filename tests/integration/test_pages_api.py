from __future__ import annotations

import uuid
import zipfile
import io

import responses
from fastapi.testclient import TestClient

from backend.main import app
from backend.api import routes_pages, routes_references, routes_progress
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


def test_page_lifecycle(monkeypatch):
    """Test complete page management workflow: scrape → list → rename → list again → delete."""
    # Setup in-memory repo and mock parser
    repo = InMemoryRepository()
    monkeypatch.setattr(routes_pages, "repo", repo, raising=True)
    monkeypatch.setattr(routes_references, "repo", repo, raising=True)
    monkeypatch.setattr(routes_progress, "repo", repo, raising=True)

    sample_html = (
        '<title>Original Title</title>'
        '<cite class="citation"><a href="https://example.com">Example</a></cite>'
    )
    monkeypatch.setattr(routes_references.parser, "fetch_html", lambda _: sample_html, raising=False)

    client = TestClient(app)

    # 1. User scrapes a Wikipedia page
    scrape_resp = client.post("/api/v1/references", json={"url": "https://en.wikipedia.org/wiki/Test"})
    assert scrape_resp.status_code == 202
    job_id = scrape_resp.json()["job_id"]

    # 2. Wait for parse to complete
    refs_resp = client.get(f"/api/v1/references/{job_id}")
    assert refs_resp.status_code == 200
    assert refs_resp.json()["title"] == "Original Title"

    # 3. User views their pages list
    pages_resp = client.get("/api/v1/pages")
    assert pages_resp.status_code == 200
    pages = pages_resp.json()
    assert len(pages) == 1
    assert pages[0]["title"] == "Original Title"
    assert pages[0]["total_refs"] == 1
    page_id = pages[0]["id"]

    # 4. User renames the page
    rename_resp = client.patch(f"/api/v1/pages/{page_id}", json={"title": "My Custom Title"})
    assert rename_resp.status_code == 200
    assert rename_resp.json()["title"] == "My Custom Title"

    # 5. User views pages list again to see the change
    pages_resp2 = client.get("/api/v1/pages")
    assert pages_resp2.status_code == 200
    assert pages_resp2.json()[0]["title"] == "My Custom Title"

    # 6. User deletes the page
    delete_resp = client.delete(f"/api/v1/pages/{page_id}")
    assert delete_resp.status_code == 204

    # 7. Verify page is gone
    pages_resp3 = client.get("/api/v1/pages")
    assert pages_resp3.status_code == 200
    assert len(pages_resp3.json()) == 0


def test_refresh_page(monkeypatch):
    """Test page refresh workflow: user refreshes page to get updated references from Wikipedia."""
    # Setup
    repo = InMemoryRepository()
    monkeypatch.setattr(routes_pages, "repo", repo, raising=True)

    # Mock parser to return different HTML on successive calls
    call_count = [0]
    def mock_fetch_html(self, url):
        call_count[0] += 1
        if call_count[0] == 1:
            return (
                '<title>Old Title</title>'
                '<cite class="citation"><a href="https://ref1.com">Ref 1</a></cite>'
            )
        else:
            return (
                '<title>Updated Title</title>'
                '<cite class="citation"><a href="https://ref1.com">Ref 1</a></cite>'
                '<cite class="citation"><a href="https://ref2.com">Ref 2</a></cite>'
                '<cite class="citation"><a href="https://ref3.com">Ref 3</a></cite>'
            )

    from backend.core.wikipedia_parser import WikipediaParser
    monkeypatch.setattr(WikipediaParser, "fetch_html", mock_fetch_html, raising=False)

    client = TestClient(app)

    # 1. User creates initial page with 1 reference
    parser = WikipediaParser()
    page = repo.create_wikipedia_page(url="https://en.wikipedia.org/wiki/Test", title="Old Title")
    refs = parser.parse(page.url)
    repo.add_references(page, refs)

    # Verify initial state
    initial_pages = client.get("/api/v1/pages").json()
    assert len(initial_pages) == 1
    assert initial_pages[0]["total_refs"] == 1
    assert initial_pages[0]["title"] == "Old Title"
    page_id = initial_pages[0]["id"]

    # 2. User clicks refresh to get updated content
    refresh_resp = client.post(f"/api/v1/pages/{page_id}/refresh")
    assert refresh_resp.status_code == 202
    assert refresh_resp.json()["refreshing"] is True

    # 3. User checks pages list again after refresh completes
    updated_pages = client.get("/api/v1/pages").json()
    assert len(updated_pages) == 1
    assert updated_pages[0]["total_refs"] == 3  # Now has 3 references
    assert updated_pages[0]["title"] == "Updated Title"  # Title updated
    assert updated_pages[0]["refreshing"] is False  # Refresh flag cleared

    # Verify the actual references were updated
    refs_resp = client.get(f"/api/v1/pages/{page_id}/references")
    assert len(refs_resp.json()["references"]) == 3


@responses.activate
def test_scrape_and_download_workflow(monkeypatch, tmp_path):
    """
    Test complete scrape-to-download workflow:
    Parse page → scrape 1 ref → download (single PDF) → 
    scrape 2 more → download (ZIP with all 3).
    """
    # Setup in-memory repo and temp storage
    repo = InMemoryRepository()
    monkeypatch.setattr(routes_pages, "repo", repo, raising=True)
    monkeypatch.setattr(routes_references, "repo", repo, raising=True)
    monkeypatch.setattr(routes_progress, "repo", repo, raising=True)

    # Mock parser to return 3 references
    sample_html = (
        '<title>Test Page</title>'
        '<cite class="citation"><a href="https://ref1.com">Ref 1</a></cite>'
        '<cite class="citation"><a href="https://ref2.com">Ref 2</a></cite>'
        '<cite class="citation"><a href="https://ref3.com">Ref 3</a></cite>'
    )
    monkeypatch.setattr(routes_references.parser, "fetch_html", lambda _: sample_html, raising=False)

    # Mock actual reference URLs
    responses.add(responses.GET, "https://ref1.com", body="<html><body>Content 1</body></html>", status=200)
    responses.add(responses.GET, "https://ref2.com", body="<html><body>Content 2</body></html>", status=200)
    responses.add(responses.GET, "https://ref3.com", body="<html><body>Content 3</body></html>", status=200)

    # Patch storage to use temp directory
    from backend.infra.storage.local_fs import LocalFileStorage as _LFS
    import backend.core.scraper as _scraper_module
    storage = _LFS(root=tmp_path)
    monkeypatch.setattr(_scraper_module, "LocalFileStorage", lambda root=None: storage, raising=True)
    monkeypatch.setattr(routes_pages, "storage", storage, raising=True)
    monkeypatch.setattr(routes_progress, "storage", storage, raising=True)

    client = TestClient(app)

    # 1. User parses Wikipedia page
    parse_resp = client.post("/api/v1/references", json={"url": "https://en.wikipedia.org/wiki/Test"})
    job_id = parse_resp.json()["job_id"]
    refs_resp = client.get(f"/api/v1/references/{job_id}").json()
    all_ref_ids = [r["id"] for r in refs_resp["references"]]
    assert len(all_ref_ids) == 3

    # Get page_id for download endpoint
    pages = client.get("/api/v1/pages").json()
    page_id = pages[0]["id"]

    # 2. User scrapes first reference
    scrape1_resp = client.post("/api/v1/scrape", json={"reference_ids": [all_ref_ids[0]], "aggressive": False})
    assert scrape1_resp.status_code == 202

    # 3. User downloads - should get single PDF
    download1_resp = client.get(f"/api/v1/pages/{page_id}/download")
    assert download1_resp.status_code == 200
    assert download1_resp.headers["content-type"] == "application/pdf"
    assert "pdf" in download1_resp.headers["content-disposition"]

    # 4. User scrapes two more references
    scrape2_resp = client.post("/api/v1/scrape", json={"reference_ids": all_ref_ids[1:], "aggressive": False})
    assert scrape2_resp.status_code == 202

    # 5. User downloads again - should now get ZIP with all 3 PDFs
    download2_resp = client.get(f"/api/v1/pages/{page_id}/download")
    assert download2_resp.status_code == 200
    assert download2_resp.headers["content-type"] == "application/zip"
    assert "references.zip" in download2_resp.headers["content-disposition"]

    # Verify ZIP contains 3 PDFs
    zip_bytes = io.BytesIO(download2_resp.content)
    with zipfile.ZipFile(zip_bytes, "r") as zf:
        names = zf.namelist()
        assert len(names) == 3
        assert all(name.endswith(".pdf") for name in names)

    # 6. Verify page summary shows correct counts
    final_pages = client.get("/api/v1/pages").json()
    assert final_pages[0]["total_refs"] == 3
    assert final_pages[0]["scraped_refs"] == 3
    assert final_pages[0]["percent_scraped"] == 100.0
