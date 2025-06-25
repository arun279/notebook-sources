from __future__ import annotations

"""Simple PDF generation helper for the MVP.

This module purposefully keeps its implementation lightweight: the final
architecture calls for Playwright's ``page.pdf``.  Until we wire that in, we
fall back to creating a trivial PDF with the page's plain-text content using
``fpdf`` so that the rest of the pipeline (storage, download, etc.) can be
exercised end-to-end.  Swapping the implementation later will not affect the
public interface.
"""

from pathlib import Path

from fpdf import FPDF  # type: ignore

# Playwright is heavy; import lazily to avoid cost when unused or unavailable.
try:
    from playwright.sync_api import sync_playwright  # type: ignore

    _HAS_PLAYWRIGHT = True
except ImportError:  # pragma: no cover – running in minimal env without Playwright
    _HAS_PLAYWRIGHT = False

from backend.infra.storage.base import AbstractStorage


class PDFService:  # noqa: WPS110 – domain term
    """Generate PDFs and persist them via :pyclass:`AbstractStorage`."""

    def __init__(self, storage: AbstractStorage) -> None:  # noqa: D401
        self._storage = storage

    # ---------------------------------------------------------------------
    # Public helpers
    # ---------------------------------------------------------------------
    def html_to_pdf(self, html: str, relative_pdf_path: Path) -> Path:  # noqa: D401
        """Render *html* into a PDF saved under *relative_pdf_path*.

        Returns the actual path as resolved by the storage adapter so that
        callers can store the information on the :pyclass:`Reference` model.
        """
        if _HAS_PLAYWRIGHT:
            try:
                return self._render_pdf_playwright(html, relative_pdf_path)
            except Exception:  # noqa: WPS429 – fall back to FPDF
                pass

        pdf_bytes = self._render_placeholder_pdf(html)
        return self._storage.save_bytes(relative_pdf_path, pdf_bytes)

    # ------------------------------------------------------------------
    # Internal implementation details
    # ------------------------------------------------------------------
    @staticmethod
    def _render_placeholder_pdf(html: str) -> bytes:  # noqa: D401
        """Very small, text-only PDF so CI builds remain fast."""
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.set_font("Arial", size=11)
        # Naively strip tags – real renderer will preserve styling
        import re

        text_content = re.sub(r"<[^>]+>", "", html)[:4000]
        pdf.multi_cell(0, 10, txt=text_content)
        # Return PDF bytes in-memory (latin-1 is FPDF internal default)
        raw = pdf.output(dest="S")
        if isinstance(raw, str):
            return raw.encode("latin1")
        return raw

    # ------------------------------------------------------------------
    # Playwright implementation
    # ------------------------------------------------------------------
    def _render_pdf_playwright(self, html: str, rel_path: Path) -> Path:  # noqa: D401
        """Render *html* to PDF using headless Chromium via Playwright."""
        # Persist HTML to a temporary file under storage so that Chromium can access it.
        tmp_html_path = rel_path.with_suffix(".html")
        self._storage.save_bytes(tmp_html_path, html.encode("utf-8"))

        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox"])
            page = browser.new_page()
            page.goto(f"file://{self._storage.root / tmp_html_path}")
            # Use sensible defaults from project plan
            pdf_bytes = page.pdf(
                format="A4",
                margin={"top": "10mm", "bottom": "10mm", "left": "12mm", "right": "12mm"},
                print_background=True,
                prefer_css_page_size=False,
            )
            browser.close()

        # Save bytes via storage adapter so path layout is consistent.
        return self._storage.save_bytes(rel_path, pdf_bytes) 