from __future__ import annotations

import abc
import uuid
from typing import Iterable, List

from backend.core import models


class AbstractRepository(abc.ABC):
    """Repository interface abstracting persistence backend."""

    # WikipediaPage

    @abc.abstractmethod
    def get_wikipedia_page_by_url(self, url: str) -> models.WikipediaPage | None:  # noqa: D401
        ...

    @abc.abstractmethod
    def create_wikipedia_page(self, url: str, title: str | None = None) -> models.WikipediaPage:
        ...

    @abc.abstractmethod
    def list_wikipedia_pages(self) -> List[models.WikipediaPage]:  # noqa: D401
        ...

    @abc.abstractmethod
    def update_wikipedia_page(self, page: models.WikipediaPage) -> None:  # noqa: D401
        ...

    @abc.abstractmethod
    def delete_wikipedia_page(self, page_id: uuid.UUID) -> None:  # noqa: D401
        ...

    @abc.abstractmethod
    def replace_references(self, page: models.WikipediaPage, refs: Iterable[models.Reference]) -> None:  # noqa: D401
        """Delete existing references for page and add new ones."""
        ...

    # References

    @abc.abstractmethod
    def add_references(self, page: models.WikipediaPage, refs: Iterable[models.Reference]) -> None:
        ...

    @abc.abstractmethod
    def list_references(self, page_id: uuid.UUID) -> List[models.Reference]:
        ...

    @abc.abstractmethod
    def update_reference(self, ref: models.Reference) -> None:
        ...

    @abc.abstractmethod
    def get_reference(self, reference_id: uuid.UUID) -> models.Reference | None:
        ... 