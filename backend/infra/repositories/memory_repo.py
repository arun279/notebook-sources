from __future__ import annotations

import uuid
from typing import Dict, List

from backend.core import models
from backend.infra.repositories.base import AbstractRepository


class InMemoryRepository(AbstractRepository):
    """Thread-unsafe in-memory repository for development/testing."""

    def __init__(self) -> None:
        self._pages: Dict[uuid.UUID, models.WikipediaPage] = {}
        self._pages_by_url: Dict[str, uuid.UUID] = {}
        self._references: Dict[uuid.UUID, models.Reference] = {}
        self._refs_by_page: Dict[uuid.UUID, List[uuid.UUID]] = {}

    # WikipediaPage methods
    def get_wikipedia_page_by_url(self, url: str) -> models.WikipediaPage | None:
        page_id = self._pages_by_url.get(url)
        if page_id:
            return self._pages[page_id]
        return None

    def create_wikipedia_page(self, url: str, title: str | None = None) -> models.WikipediaPage:
        page = models.WikipediaPage(url=url, title=title)
        assert page.id is not None  # sqlmodel gives uuid
        self._pages[page.id] = page
        self._pages_by_url[url] = page.id
        self._refs_by_page[page.id] = []
        return page

    # Reference methods

    def add_references(self, page: models.WikipediaPage, refs: List[models.Reference]) -> None:  # type: ignore[override]
        for ref in refs:
            if ref.id is None:
                ref.id = uuid.uuid4()
            # ensure FK set so downstream lookups know the owning page
            ref.wiki_page_id = page.id  # type: ignore[assignment]
            self._references[ref.id] = ref
            self._refs_by_page.setdefault(page.id, []).append(ref.id)  # type: ignore[arg-type]

    def list_references(self, page_id: uuid.UUID) -> List[models.Reference]:
        ids = self._refs_by_page.get(page_id, [])
        return [self._references[rid] for rid in ids]

    def update_reference(self, ref: models.Reference) -> None:
        assert ref.id is not None
        self._references[ref.id] = ref

    def get_reference(self, reference_id: uuid.UUID) -> models.Reference | None:
        return self._references.get(reference_id) 