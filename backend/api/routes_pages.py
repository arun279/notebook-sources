from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, HTTPException, Response, status, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse

from backend.api.schemas import PageSummary, ReferencesResponse, ReferenceDTO
from backend.settings import settings
from backend.core.models import ReferenceStatus
from backend.infra.tasks.inline import InlineTaskQueue
from backend.core.wikipedia_parser import WikipediaParser
from backend.infra.storage.local_fs import LocalFileStorage

if str(settings.database_url).startswith("sqlite"):
    from backend.infra.repositories.sql_repo import SQLRepository as _Repo  # noqa: WPS433
else:
    from backend.infra.repositories.memory_repo import InMemoryRepository as _Repo  # noqa: WPS433

repo = _Repo()

router = APIRouter(prefix="/api/v1", tags=["pages"])

storage = LocalFileStorage()


@router.get("/pages", response_model=List[PageSummary])
async def list_pages() -> List[PageSummary]:  # noqa: D401
    pages = repo.list_wikipedia_pages()
    summaries: list[PageSummary] = []
    for p in pages:
        refs = repo.list_references(p.id)  # type: ignore[arg-type]
        total = len(refs)
        scraped = sum(1 for r in refs if r.status == ReferenceStatus.scraped)
        percent = (scraped / total * 100) if total else 0.0
        summaries.append(PageSummary(
            id=p.id,  # type: ignore[arg-type]
            url=p.url,
            title=p.title,
            total_refs=total,
            scraped_refs=scraped,
            percent_scraped=percent,
        ))
    return summaries


# ---------------- References by page ----------------


@router.get("/pages/{page_id}/references", response_model=ReferencesResponse)
async def references_by_page(page_id: uuid.UUID) -> ReferencesResponse:  # noqa: D401
    page = repo.list_references(page_id)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")
    refs = repo.list_references(page_id)
    dtos = [ReferenceDTO.model_validate(r) for r in refs]  # type: ignore[arg-type]
    return ReferencesResponse(references=dtos)


# ---------------- Delete page ----------------


@router.delete(
    "/pages/{page_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_page(page_id: uuid.UUID) -> Response:  # noqa: D401
    try:
        repo.delete_wikipedia_page(page_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Page not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------- Rename page ----------------


from pydantic import BaseModel


class _RenameReq(BaseModel):
    title: str


@router.patch("/pages/{page_id}", response_model=PageSummary)
async def rename_page(page_id: uuid.UUID, body: _RenameReq):  # noqa: D401
    page_list = [p for p in repo.list_wikipedia_pages() if p.id == page_id]
    if not page_list:
        raise HTTPException(status_code=404, detail="Page not found")
    page = page_list[0]
    page.title = body.title
    repo.update_wikipedia_page(page)
    # return updated summary
    refs = repo.list_references(page_id)
    total = len(refs)
    scraped = sum(1 for r in refs if r.status == ReferenceStatus.scraped)
    return PageSummary(
        id=page.id,
        url=page.url,
        title=page.title,
        total_refs=total,
        scraped_refs=scraped,
        percent_scraped=(scraped / total * 100) if total else 0.0,
    )


# ---------------- Refresh page ----------------


@router.post("/pages/{page_id}/refresh", status_code=status.HTTP_202_ACCEPTED)
async def refresh_page(page_id: uuid.UUID, bg: BackgroundTasks) -> PageSummary:  # noqa: D401
    page_list = [p for p in repo.list_wikipedia_pages() if p.id == page_id]
    if not page_list:
        raise HTTPException(status_code=404, detail="Page not found")
    page = page_list[0]

    def job() -> None:
        parser = WikipediaParser()
        new_refs = parser.parse(page.url)
        if parser.last_title:
            page.title = parser.last_title  # type: ignore[assignment]
            repo.update_wikipedia_page(page)
        repo.replace_references(page, new_refs)

    InlineTaskQueue(bg).enqueue(job)

    # Return immediate summary (old counts) so UI can keep going
    refs = repo.list_references(page_id)
    total = len(refs)
    scraped = sum(1 for r in refs if r.status == ReferenceStatus.scraped)
    return PageSummary(
        id=page.id,
        url=page.url,
        title=page.title,
        total_refs=total,
        scraped_refs=scraped,
        percent_scraped=(scraped / total * 100) if total else 0.0,
    )


# --------------- Download all scraped refs for page -----------------


import io, zipfile, pathlib, concurrent.futures


@router.get("/pages/{page_id}/download")
async def download_page_zip(page_id: uuid.UUID):  # noqa: D401
    refs = repo.list_references(page_id)
    scraped = [r for r in refs if r.status == ReferenceStatus.scraped and r.pdf_path]
    if not scraped:
        raise HTTPException(status_code=404, detail="No PDFs available for this page")

    if len(scraped) == 1:
        ref = scraped[0]
        abs_path = storage.root / pathlib.Path(ref.pdf_path)  # type: ignore[arg-type]
        return FileResponse(abs_path, filename=f"{ref.id}.pdf", media_type="application/pdf")

    # ---------------------------------------------------------------------
    # Read files concurrently so that large sets of PDFs are fetched from
    # disk in parallel, improving total response time when many references
    # are involved.  We first load the bytes into memory and then write them
    # to the in-memory ZIP so that ZipFile doesn't perform one blocking read
    # per file.
    # ---------------------------------------------------------------------
    def _load(ref):  # noqa: D401 – local helper
        path = storage.root / pathlib.Path(ref.pdf_path)  # type: ignore[arg-type]
        return ref.id, path.read_bytes()

    with concurrent.futures.ThreadPoolExecutor() as pool:
        loaded = list(pool.map(_load, scraped))

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for ref_id, data in loaded:
            zf.writestr(f"{ref_id}.pdf", data)
    zip_buffer.seek(0)
    return StreamingResponse(zip_buffer, media_type="application/zip", headers={"Content-Disposition": "attachment; filename=references.zip"}) 