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