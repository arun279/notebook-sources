from __future__ import annotations

import uuid
from typing import Iterable, List
from pathlib import Path
from urllib.parse import urlparse

from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy import delete as sqla_delete

from backend.core import models
from backend.infra.repositories.base import AbstractRepository
from backend.settings import settings


class SQLRepository(AbstractRepository):
    """SQLModel-powered repository supporting SQLite/Postgres."""

    def __init__(self) -> None:
        from urllib.parse import urlparse

        db_url = str(settings.database_url)
        # When using a file-based SQLite URL, ensure parent directory exists so
        # that tests (and the app) do not error with "unable to open database file".
        if db_url.startswith("sqlite") and ":memory:" not in db_url:
            # sqlite:///absolute/path OR sqlite:///./relative/path
            parsed = urlparse(db_url)
            # remove leading '/' from path on Windows-like paths in URL
            file_path = parsed.path
            if file_path:
                Path(file_path).parent.mkdir(parents=True, exist_ok=True)

        self.engine = create_engine(db_url, echo=False)
        SQLModel.metadata.create_all(self.engine)

    def _session(self) -> Session:  # context manager alias
        return Session(self.engine, expire_on_commit=False)

    # WikipediaPage
    def get_wikipedia_page_by_url(self, url: str) -> models.WikipediaPage | None:  # noqa: D401
        with self._session() as session:
            statement = select(models.WikipediaPage).where(models.WikipediaPage.url == url)
            return session.exec(statement).first()

    def create_wikipedia_page(self, url: str, title: str | None = None) -> models.WikipediaPage:
        page = models.WikipediaPage(url=url, title=title)
        with self._session() as session:
            session.add(page)
            session.commit()
            session.refresh(page)
        return page

    def update_wikipedia_page(self, page: models.WikipediaPage) -> None:  # type: ignore[override]
        with self._session() as session:
            session.add(page)
            session.commit()

    # References
    def add_references(self, page: models.WikipediaPage, refs: Iterable[models.Reference]) -> None:
        with self._session() as session:
            to_add: list[models.Reference] = []
            for ref in refs:
                ref.wiki_page_id = page.id  # type: ignore[assignment]
                to_add.append(ref)
            session.add_all(to_add)
            session.commit()

    def list_references(self, page_id: uuid.UUID) -> List[models.Reference]:
        with self._session() as session:
            stmt = select(models.Reference).where(models.Reference.wiki_page_id == page_id)
            return list(session.exec(stmt).all())

    def update_reference(self, ref: models.Reference) -> None:
        with self._session() as session:
            session.add(ref)
            session.commit()

    def get_reference(self, reference_id: uuid.UUID) -> models.Reference | None:
        with self._session() as session:
            return session.get(models.Reference, reference_id)

    # Wikipedia pages list
    def list_wikipedia_pages(self) -> List[models.WikipediaPage]:  # type: ignore[override]
        with self._session() as session:
            stmt = select(models.WikipediaPage)
            return list(session.exec(stmt).all())

    def delete_wikipedia_page(self, page_id: uuid.UUID) -> None:  # type: ignore[override]
        with self._session() as session:
            page = session.get(models.WikipediaPage, page_id)
            if page is None:
                return
            # Delete references first due to FK constraint (SQLModel defaults to restrict)
            session.exec(sqla_delete(models.Reference).where(models.Reference.wiki_page_id == page_id))
            session.delete(page)
            session.commit()

    def replace_references(self, page: models.WikipediaPage, refs: Iterable[models.Reference]) -> None:  # type: ignore[override]
        with self._session() as session:
            # Delete existing refs
            session.exec(sqla_delete(models.Reference).where(models.Reference.wiki_page_id == page.id))
            # Add new refs
            for ref in refs:
                ref.wiki_page_id = page.id  # type: ignore[assignment]
            session.add_all(list(refs))
            session.commit() 