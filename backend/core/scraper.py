from __future__ import annotations

"""Minimal Scraper implementation wiring together archive resolver + pdf service.

It purposefully keeps external dependencies to the standard library + ``requests``.
When a reference URL is determined paywalled, the scraper *attempts* the archive
resolver but happily proceeds with the live page if resolution fails.  The
return value is a tuple ``(success, error_message)`` and the caller is
responsible for mutating the :pyclass:`backend.core.models.Reference` instance.
"""

from datetime import datetime
from pathlib import Path
from typing import Tuple, TYPE_CHECKING

import requests

from backend.core.archive_resolver import ArchiveResolver
from backend.core.pdf_service import PDFService
from backend.core import models
from backend.infra.storage.local_fs import LocalFileStorage
from backend.settings import settings

if TYPE_CHECKING:
    from backend.core.browser_pool import AsyncBrowserPool


class Scraper:  # noqa: WPS110 – domain term
    """Download a reference, render a PDF, and persist artefacts."""

    def __init__(self, job_id: str, browser_pool: AsyncBrowserPool | None = None) -> None:  # noqa: D401
        self._storage = LocalFileStorage()  # root = settings.data_dir by default
        self._resolver = ArchiveResolver()
        self._pdf = PDFService(self._storage, browser_pool)
        self._job_root = Path("jobs") / job_id

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def scrape(self, ref: models.Reference, aggressive: bool = False) -> Tuple[bool, str | None]:  # noqa: D401,E501
        """Return *(success, error)* tuple."""
        try:
            html, source_url = self._fetch_html(ref, aggressive)

            # Persist raw HTML
            raw_rel_path = self._raw_path(ref)
            self._storage.save_bytes(raw_rel_path, html.encode("utf-8"))
            ref.html_path = str(raw_rel_path)

            # Generate PDF
            pdf_rel_path = self._pdf_path(ref)
            abs_pdf_path = self._pdf.html_to_pdf(html, pdf_rel_path)
            ref.pdf_path = str(pdf_rel_path)

            ref.scraped_at = datetime.utcnow()
            ref.status = models.ReferenceStatus.scraped

            if source_url != ref.url:
                ref.archive_source = source_url
                ref.archive_timestamp = datetime.utcnow()
            return True, None
        except Exception as exc:  # noqa: WPS429 – broad except to capture network etc.
            ref.status = models.ReferenceStatus.failed
            error_msg = exc.__class__.__name__ + ": " + str(exc)
            ref.error = error_msg
            return False, error_msg

    # ------------------------------------------------------------------
    # Internals helpers
    # ------------------------------------------------------------------
    def _fetch_html(self, ref: models.Reference, aggressive: bool) -> tuple[str, str]:  # noqa: D401,E501
        """Fetch HTML, prioritising archive when paywalled."""
        # 1. If flagged paywalled, try archive first
        if ref.suspected_paywall:
            outcome = self._resolver.resolve(ref.url, True, aggressive)
            if outcome.success and outcome.html:
                return outcome.html, outcome.archive_url or ref.url

        # 2. Attempt live fetch
        try:
            resp = requests.get(ref.url, timeout=30)
            resp.raise_for_status()
            return resp.text, ref.url
        except requests.HTTPError as http_err:
            # On auth / paywall errors, fallback to archive resolver
            if http_err.response.status_code in {401, 402, 403, 451}:
                outcome = self._resolver.resolve(ref.url, ref.suspected_paywall, aggressive)
                if outcome.success and outcome.html:
                    return outcome.html, outcome.archive_url or ref.url
            raise

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------
    def _raw_path(self, ref: models.Reference) -> Path:
        return self._job_root / "raw" / f"{ref.id}.html"

    def _pdf_path(self, ref: models.Reference) -> Path:
        return self._job_root / "pdf" / f"{ref.id}.pdf" 