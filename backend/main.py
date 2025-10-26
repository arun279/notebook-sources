from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from backend.api import routes_references
from backend.api import routes_progress
from backend.api import routes_pages
from backend.settings import settings

app = FastAPI(title="Notebook References API", version="0.1.0")

# CORS for local dev React app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*" if settings.env == "dev" else ""],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_references.router)
app.include_router(routes_progress.router)
app.include_router(routes_pages.router)

# ---------------------------------------------------------------------------
# Serve React SPA (built via `npm run build`)
# ---------------------------------------------------------------------------
ui_dist = Path(__file__).parent.parent / "ui" / "dist"
if ui_dist.exists():
    app.mount("/", StaticFiles(directory=ui_dist, html=True), name="spa")

@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:  # noqa: D401
    return RedirectResponse(url="/docs") 