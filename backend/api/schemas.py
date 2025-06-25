from __future__ import annotations

import uuid
from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field
from pydantic import ConfigDict

from backend.core.models import ReferenceStatus


class ParseRequest(BaseModel):
    url: str


class JobResponse(BaseModel):
    job_id: uuid.UUID


class ReferenceDTO(BaseModel):
    id: uuid.UUID
    title: str
    url: str
    pub_date: Optional[date] = None
    access_date: Optional[date] = None
    suspected_paywall: bool = False
    status: ReferenceStatus = Field(default=ReferenceStatus.pending)

    model_config = ConfigDict(from_attributes=True)


class ReferencesResponse(BaseModel):
    references: List[ReferenceDTO]


class ScrapeRequest(BaseModel):
    reference_ids: List[uuid.UUID]
    aggressive: bool = False


class ReferenceProgress(BaseModel):
    reference_id: uuid.UUID
    status: ReferenceStatus

    model_config = ConfigDict(json_encoders=None)  # Enum serialises as str by default


class ProgressResponse(BaseModel):
    percent: float
    items: List[ReferenceProgress]


# ---------------- Dashboard ----------------


class PageSummary(BaseModel):
    id: uuid.UUID
    url: str
    title: str | None = None
    total_refs: int
    scraped_refs: int
    percent_scraped: float
    refreshing: bool = False 