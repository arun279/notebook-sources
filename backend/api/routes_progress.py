from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from typing import Dict, List
from pathlib import Path
import uuid
import io
import zipfile
import concurrent.futures

from backend.api.schemas import ProgressResponse, ReferenceProgress
from backend.core.models import ReferenceStatus
from backend.infra.repositories.sql_repo import SQLRepository  # Assuming SQLite for MVP
from backend.infra.storage.local_fs import LocalFileStorage
from backend.api.routes_references import job_page_map  # reuse mapping

repo = SQLRepository()
storage = LocalFileStorage()

router = APIRouter(prefix="/api/v1", tags=["progress"])

# ---------------------------------------------------------------------------
# In-memory websocket connection store
# ---------------------------------------------------------------------------
class _ConnectionManager:
    def __init__(self) -> None:  # noqa: D401
        self.active: Dict[uuid.UUID, List[WebSocket]] = {}

    async def connect(self, job_id: uuid.UUID, websocket: WebSocket) -> None:  # noqa: D401
        await websocket.accept()
        self.active.setdefault(job_id, []).append(websocket)

    def disconnect(self, job_id: uuid.UUID, websocket: WebSocket) -> None:  # noqa: D401
        self.active.get(job_id, []).remove(websocket)

    async def broadcast(self, job_id: uuid.UUID, message: dict) -> None:  # noqa: D401
        for ws in list(self.active.get(job_id, [])):
            await ws.send_json(message)


ws_manager = _ConnectionManager()

# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------


@router.get("/progress/{job_id}", response_model=ProgressResponse)
async def get_progress(job_id: uuid.UUID) -> ProgressResponse:  # noqa: D401
    page_id = job_page_map.get(job_id)
    if page_id is None:
        raise HTTPException(status_code=404, detail="Job not found")
    refs = repo.list_references(page_id)
    total = len(refs) or 1  # avoid div-by-zero
    completed = sum(1 for r in refs if r.status in {ReferenceStatus.scraped, ReferenceStatus.failed, ReferenceStatus.blocked})
    percent = completed / total * 100
    items = [ReferenceProgress(reference_id=r.id, status=r.status) for r in refs]  # type: ignore[arg-type]
    return ProgressResponse(percent=percent, items=items)


@router.get("/download")
async def download(ids: str | None = None, all: bool = False):  # noqa: D401
    """Download one PDF or a ZIP when multiple IDs given.

    ``ids`` – comma-separated UUIDs as a query parameter.
    """
    if not all and not ids:
        raise HTTPException(status_code=400, detail="Provide ?ids or ?all=true")

    if all:
        # Not efficient but acceptable for MVP – fetch all scraped refs
        references = []
        for page_id in job_page_map.values():
            references.extend(repo.list_references(page_id))
    else:
        ref_ids = [uuid.UUID(i) for i in ids.split(",")]
        references = [repo.get_reference(rid) for rid in ref_ids if repo.get_reference(rid)]

    # Remove duplicate IDs to avoid duplicate filenames in the ZIP which triggers a warning.
    unique_refs = {}
    for r in references:
        if r.id not in unique_refs and r.pdf_path and storage.exists(Path(r.pdf_path)):  # type: ignore[arg-type]
            unique_refs[r.id] = r

    pdf_files = list(unique_refs.values())
    if not pdf_files:
        raise HTTPException(status_code=404, detail="No PDFs available for given IDs")

    if len(pdf_files) == 1 and not all:
        ref = pdf_files[0]
        abs_path = storage.root / Path(ref.pdf_path)  # type: ignore[arg-type]
        return FileResponse(abs_path, filename=f"{ref.id}.pdf", media_type="application/pdf")

    # multiple – stream ZIP, reading files concurrently to speed-up I/O when
    # many PDFs are requested.
    def _read(ref):  # noqa: D401 – helper
        return ref.id, (storage.root / Path(ref.pdf_path)).read_bytes()  # type: ignore[arg-type]

    with concurrent.futures.ThreadPoolExecutor() as pool:
        loaded = list(pool.map(_read, pdf_files))

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for ref_id, data in loaded:
            zf.writestr(f"{ref_id}.pdf", data)
    zip_buffer.seek(0)
    return StreamingResponse(zip_buffer, media_type="application/zip", headers={"Content-Disposition": "attachment; filename=bundle.zip"})


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------


@router.websocket("/ws/progress/{job_id}")
async def ws_progress(websocket: WebSocket, job_id: uuid.UUID):  # noqa: D401
    await ws_manager.connect(job_id, websocket)
    try:
        while True:
            await websocket.receive_text()  # keep alive, ignore content
    except WebSocketDisconnect:
        ws_manager.disconnect(job_id, websocket) 