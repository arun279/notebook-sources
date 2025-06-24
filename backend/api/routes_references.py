from __future__ import annotations

import uuid
from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from typing import Dict

from backend.api.schemas import (JobResponse, ParseRequest, ReferencesResponse,
                                 ReferenceDTO, ScrapeRequest)
from backend.core.wikipedia_parser import WikipediaParser
from backend.settings import settings
from backend.infra.tasks.inline import InlineTaskQueue

# Repository backend choice – SQLite file or in-memory
if str(settings.database_url).startswith("sqlite"):
    from backend.infra.repositories.sql_repo import SQLRepository  # noqa: WPS433

    repo = SQLRepository()
else:
    from backend.infra.repositories.memory_repo import InMemoryRepository  # noqa: WPS433

    repo = InMemoryRepository()

parser = WikipediaParser()

# In-process mapping of job_id -> page_id until a proper Job table is added.
job_page_map: Dict[uuid.UUID, uuid.UUID] = {}

router = APIRouter(prefix="/api/v1", tags=["references"])


@router.post("/references", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
async def parse_references(req: ParseRequest, bg: BackgroundTasks) -> JobResponse:  # noqa: D401
    """Start background job that fetches and parses the Wikipedia article."""

    task_queue = InlineTaskQueue(bg)
    job_id = uuid.uuid4()

    def job() -> None:  # inner sync function executed later
        page = repo.get_wikipedia_page_by_url(req.url) or repo.create_wikipedia_page(req.url)
        refs = parser.parse(req.url)
        repo.add_references(page, refs)
        job_page_map[job_id] = page.id  # type: ignore[attr-defined]

    task_queue.enqueue(job)
    return JobResponse(job_id=job_id)


@router.get("/references/{job_id}", response_model=ReferencesResponse)
async def get_references(job_id: uuid.UUID) -> ReferencesResponse:  # noqa: D401
    page_id = job_page_map.get(job_id)
    if page_id is None:
        raise HTTPException(status_code=404, detail="Job not found or not completed yet")
    refs = repo.list_references(page_id)
    dtos = [ReferenceDTO.model_validate(r) for r in refs]  # type: ignore[arg-type]
    return ReferencesResponse(references=dtos)


@router.post("/scrape", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
async def scrape_references(req: ScrapeRequest, bg: BackgroundTasks) -> JobResponse:  # noqa: D401
    job_id = uuid.uuid4()
    # For MVP: just mark status scraped without actual scraping

    def job() -> None:
        for ref_id in req.reference_ids:
            ref = repo.get_reference(ref_id)
            if ref:
                ref.status = "scraped"  # type: ignore[assignment]
                repo.update_reference(ref)

    InlineTaskQueue(bg).enqueue(job)
    return JobResponse(job_id=job_id) 