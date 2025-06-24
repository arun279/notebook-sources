from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlmodel import Field, SQLModel


class ReferenceStatus(str, enum.Enum):
    pending = "pending"
    scraped = "scraped"
    failed = "failed"
    blocked = "blocked"


class WikipediaPage(SQLModel, table=True):
    id: uuid.UUID | None = Field(default_factory=uuid.uuid4, primary_key=True)
    url: str = Field(index=True, unique=True)
    title: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Reference(SQLModel, table=True):
    id: uuid.UUID | None = Field(default_factory=uuid.uuid4, primary_key=True)
    wiki_page_id: uuid.UUID = Field(foreign_key="wikipediapage.id", index=True)

    title: str | None = None
    url: str
    pub_date: date | None = None
    access_date: date | None = None
    suspected_paywall: bool = False

    status: ReferenceStatus = ReferenceStatus.pending
    pdf_path: str | None = None
    html_path: str | None = None

    archive_source: str | None = None
    archive_timestamp: datetime | None = None

    error: str | None = None
    scraped_at: datetime | None = None 