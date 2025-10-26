from __future__ import annotations

import uuid
from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from typing import Dict
from pathlib import Path

from backend.api.schemas import (JobResponse, ParseRequest, ReferencesResponse,
                                 ReferenceDTO, ScrapeRequest)
from backend.core.wikipedia_parser import WikipediaParser
from backend.settings import settings
from backend.infra.tasks.inline import InlineTaskQueue
from backend.core.models import ReferenceStatus
from backend.infra.storage.local_fs import LocalFileStorage

# Repository backend choice – SQLite file or in-memory
if str(settings.database_url).startswith("sqlite"):
    from backend.infra.repositories.sql_repo import SQLRepository  # noqa: WPS433

    repo = SQLRepository()
else:
    from backend.infra.repositories.memory_repo import InMemoryRepository  # noqa: WPS433

    repo = InMemoryRepository()

storage = LocalFileStorage()
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
        if parser.last_title and not page.title:
            page.title = parser.last_title  # type: ignore[assignment]
            repo.update_wikipedia_page(page)
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

        import asyncio
        # We'll submit scrape tasks to a thread pool so that multiple
        # references can be processed concurrently according to the
        # MAX_CONCURRENT_SCRAPES setting.

        import concurrent.futures

        # First, mark all selected refs as scraping and broadcast. Doing
        # this upfront gives immediate UI feedback for *every* row rather
        # than waiting for sequential updates.
        for ref_id in req.reference_ids:
            r = repo.get_reference(ref_id)
            if r is None:
                continue
            r.status = ReferenceStatus.scraping
            repo.update_reference(r)
            asyncio.run(ws_manager.broadcast(job_id, {
                "event": "progress_update",
                "reference_id": str(ref_id),
                "status": "scraping",
            }))

        def _do_scrape(rid: uuid.UUID):  # noqa: D401
            ref_obj = repo.get_reference(rid)
            if ref_obj is None:
                return rid, False, "not-found"
            success, err = scraper.scrape(ref_obj, req.aggressive)
            repo.update_reference(ref_obj)
            return rid, success, err

        with concurrent.futures.ThreadPoolExecutor(max_workers=settings.max_concurrent_scrapes) as pool:
            futures = {pool.submit(_do_scrape, rid): rid for rid in req.reference_ids}
            for fut in concurrent.futures.as_completed(futures):
                rid = futures[fut]
                try:
                    _, success, err_msg = fut.result()
                except Exception as exc:
                    success = False
                    err_msg = str(exc)

                status_val = "scraped" if success else "failed"
                asyncio.run(ws_manager.broadcast(job_id, {
                    "event": "reference_done",
                    "reference_id": str(rid),
                    "status": status_val,
                    "error": err_msg,
                }))

        # Job done summary
        page_id = job_page_map.get(job_id)
        if page_id:
            refs_local = repo.list_references(page_id)
            successes = sum(1 for r in refs_local if r.status == ReferenceStatus.scraped)
            failures = sum(1 for r in refs_local if r.status == ReferenceStatus.failed)
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


@router.delete("/references/{reference_id}", status_code=status.HTTP_204_NO_CONTENT)
async def reset_reference_status(reference_id: uuid.UUID):
    """Delete a reference's scraped artifacts and reset its status to pending."""
    ref = repo.get_reference(reference_id)
    if ref is None:
        raise HTTPException(status_code=404, detail="Reference not found")

    if ref.pdf_path:
        storage.delete(Path(ref.pdf_path))
    if ref.html_path:
        storage.delete(Path(ref.html_path))

    ref.status = ReferenceStatus.pending
    ref.pdf_path = None
    ref.html_path = None
    ref.archive_source = None
    ref.archive_timestamp = None
    ref.error = None
    ref.scraped_at = None

    repo.update_reference(ref)
    return