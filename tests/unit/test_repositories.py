from __future__ import annotations

from backend.infra.repositories.memory_repo import InMemoryRepository
from backend.infra.repositories.sql_repo import SQLRepository
from backend.core import models
from backend.settings import settings


def _make_refs(n=3):
    return [models.Reference(url=f"https://example.com/{i}") for i in range(n)]


def test_memory_repository_round_trip():
    repo = InMemoryRepository()
    page = repo.create_wikipedia_page("https://en.wikipedia.org/wiki/Dummy")
    refs = _make_refs()
    repo.add_references(page, refs)

    listed = repo.list_references(page.id)
    assert len(listed) == len(refs)

    ref = listed[0]
    ref.status = models.ReferenceStatus.scraped
    repo.update_reference(ref)
    fetched = repo.get_reference(ref.id)
    assert fetched.status == models.ReferenceStatus.scraped


def test_sql_repository_round_trip(tmp_path, monkeypatch):
    # point DATABASE_URL to an on-disk sqlite db under tmp_path
    db_url = f"sqlite:///{tmp_path}/test.db"
    monkeypatch.setattr(settings, "database_url", db_url, raising=False)

    repo = SQLRepository()
    page = repo.create_wikipedia_page("https://en.wikipedia.org/wiki/Dummy")
    refs = _make_refs(2)
    repo.add_references(page, refs)
    listed = repo.list_references(page.id)
    assert len(listed) == 2

    first = listed[0]
    first.status = models.ReferenceStatus.failed
    repo.update_reference(first)
    again = repo.get_reference(first.id)
    assert again.status == models.ReferenceStatus.failed 