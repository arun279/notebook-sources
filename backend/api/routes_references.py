from __future__ import annotations

import uuid
from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from typing import Dict

from backend.api.schemas import (JobResponse, ParseRequest, ReferencesResponse,
                                 ReferenceDTO, ScrapeRequest)
from backend.core.wikipedia_parser import WikipediaParser
from backend.settings import settings
from backend.infra.tasks.inline import InlineTaskQueue
from backend.core.models import ReferenceStatus

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

    # Pre-map job_id to the page of first reference so /progress works immediately.
    if req.reference_ids:
        first_ref = repo.get_reference(req.reference_ids[0])
        if first_ref is not None:
            job_page_map[job_id] = first_ref.wiki_page_id  # type: ignore[arg-type]

    def job() -> None:
        from backend.core.scraper import Scraper  # local import to avoid heavy deps at startup
        from backend.api.routes_progress import ws_manager  # for broadcast

        scraper = Scraper(str(job_id))
        # Map this scrape job to the wiki page id (first reference)
        if req.reference_ids:
            first_ref = repo.get_reference(req.reference_ids[0])
            if first_ref is not None:
                job_page_map[job_id] = first_ref.wiki_page_id  # type: ignore[arg-type]
        for ref_id in req.reference_ids:
            ref = repo.get_reference(ref_id)
            if ref is None:
                continue

            # mark as "scraping" before starting
            ref.status = ReferenceStatus.scraping
            repo.update_reference(ref)
            # broadcast
            import asyncio, uuid as _uuid

            asyncio.run(ws_manager.broadcast(job_id, {
                "event": "progress_update",
                "reference_id": str(ref_id),
                "status": "scraping",
            }))

            success, error_msg = scraper.scrape(ref, req.aggressive)
            repo.update_reference(ref)

            asyncio.run(ws_manager.broadcast(job_id, {
                "event": "reference_done",
                "reference_id": str(ref_id),
                "status": ref.status.value,
                "error": error_msg,
            }))

        # Job done summary
        page_id = job_page_map.get(_uuid.UUID(str(job_id)))
        if page_id:
            refs = repo.list_references(page_id)
            successes = sum(1 for r in refs if r.status == ReferenceStatus.scraped)
            failures = sum(1 for r in refs if r.status == ReferenceStatus.failed)
        else:
            successes = failures = 0
        asyncio.run(ws_manager.broadcast(job_id, {
            "event": "job_complete",
            "job_id": str(job_id),
            "successes": successes,
            "failures": failures,
        }))

    InlineTaskQueue(bg).enqueue(job)
    return JobResponse(job_id=job_id) 