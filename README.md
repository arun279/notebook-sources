# Notebook-References

This is a work in progress project to build a web application that allows users to scrape Wikipedia articles and extract references and export it in a format that's friendly to LLMs.

This repository currentlycontains the **FastAPI** backend for the *Notebook References* MVP along with a comprehensive test-suite and Docker workflow.

---

## 1  Architecture overview

Current state:

```
┌──────────┐  REST (+ WS)  ┌──────────────────────────┐
│  React   │ ───────────▶ │     FastAPI server       │
│  SPA     │              │  • Routes (/references)  │
└──────────┘              │  • BackgroundTasks       │
                          │  • InlineTaskQueue       │
                          │  • SQLModel (SQLite)     │
                          │  • LocalFileStorage      │
                          └──────────────────────────┘
```

Key abstractions (upgrade path ready):

* **Repository** (`infra/repositories/*`) – swap SQLite → Postgres.
* **TaskQueue** (`infra/tasks/*`) – swap Inline → Celery.
* **StorageAdapter** (`infra/storage/*`) – swap Local FS → S3.

---

## 2  Implemented endpoints

| Method | Path | Purpose |
| ------ | ---- | -------- |
| POST   | `/api/v1/pages` | Submit a Wikipedia URL & start reference parsing job (returns `job_id`). |
| GET    | `/api/v1/pages` | List stored pages with summary counts (`refreshing` flag). |
| PATCH  | `/api/v1/pages/{page_id}` | Rename a page. |
| POST   | `/api/v1/pages/{page_id}/refresh` | Re‐parse a page (non-blocking, UI shows pulse while `refreshing=true`). |
| DELETE | `/api/v1/pages/{page_id}` | Delete a page and its references. |
| GET    | `/api/v1/pages/{page_id}/download` | Download all scraped PDFs for a page (ZIP). |
| GET    | `/api/v1/pages/{page_id}/references` | Return the reference list for a page. |
| POST   | `/api/v1/scrape` | Scrape selected references concurrently, generate PDFs. |
| GET    | `/api/v1/progress/{job_id}` | Poll scrape progress (or consume WS). |
| WS     | `/api/v1/ws/progress/{job_id}` | Real-time scrape events. |
| GET    | `/api/v1/download` | Download arbitrary PDFs (`?ids=`) or ZIP (`?ids=,`). |

`openapi.yaml` is derived from these routes; Swagger UI available at
`http://localhost:8000/docs` when the container is running.

---

## 3  Running locally with Docker

```bash
# Build images (backend, UI & tests)
docker compose build

# Launch API (http://localhost:8000) **and** UI (http://localhost:3000)
docker compose up
```

The stack now includes three services:

* **api** – FastAPI backend on port 8000.
* **ui** – Vite dev server with React SPA on port 3000 (hot-reload enabled via bind-mount).
* **tests** – On-demand PyTest execution (`docker compose run --rm tests`).

The UI automatically proxies API requests to `http://localhost:8000` through the `VITE_API_ROOT` env variable set in *docker-compose.yml*.

Environment defaults (see `backend/settings.py`):

* `DATABASE_URL` → `sqlite:////data/notebookrefs.db`
* `DATA_DIR`     → `/data`

Both `/backend` and `/data` are bind-mounted by `docker-compose.yml` to allow
hot-reload during development.

---

## 4  Test suite

### 4.1  What is covered

* **Unit (≥ 90 % core coverage):**
  * Wikipedia parser (property-based via *Hypothesis*).
  * PDF service (FPDF placeholder).
  * Scraper: happy-path, pay-wall, HTTP-error.
  * Repository implementations (memory & SQLite).
  * Inline task queue.
  * Archive resolver stub.
* **Integration:**
  * Wikipedia → references round-trip.
  * Scrape flow with progress polling.
  * Download endpoint (PDF & ZIP variants).

All external effects (network, file-system, DB) are stubbed or redirected to
`tmp_path` so the suite is deterministic and executes in ~6 s on a cold Docker
cache.

### 4.2  Running the tests (Docker only)

A **dedicated `tests` service** is defined in *docker-compose.yml* (builds the
same image). Run once:

```bash
# Build image (runs `pip install -r requirements.txt`)
docker compose build tests

# Execute tests + coverage gate
docker compose run --rm tests
```

The command executed inside the container is:

```bash
pytest -q --cov=backend tests
```

* Coverage threshold: **85 %** (configured in `tests/conftest.py`).
* Build fails on any test failure or coverage regression.

---

## 5  Directory layout (backend only)

```
backend/
├─ api/                 # FastAPI routes & Pydantic schemas
├─ core/                # Framework-free business logic
├─ infra/               # Adapters (repo, storage, tasks)
├─ settings.py          # Pydantic BaseSettings
└─ main.py              # FastAPI application factory
```

Tests live under `tests/` and mirror the unit/integration split described in
the spec.

---

## 6 TODOs

- [ ] Add testing for the UI
- [ ] implement scraping to be more robust
- [ ] add a date range filter to the references

---

## 7  Future upgrades

Thanks to the adapter pattern, moving to Postgres + Celery + S3 only requires:

1. Provide new env vars (`DATABASE_URL`, `QUEUE_BROKER`, S3 creds).
2. Drop‐in new adapter implementations; no route code changes.

---

## 8  Troubleshooting

* **Unable to open SQLite file** – ensure the `/data` directory is writable or
  override `DATABASE_URL=sqlite:///./local.db`.
* **Playwright errors** – container base image bundles browsers; prune volumes
  if caches get corrupted.

---