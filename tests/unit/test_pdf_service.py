from __future__ import annotations

from pathlib import Path

from backend.core.pdf_service import PDFService
from backend.infra.storage.local_fs import LocalFileStorage


def test_pdf_generation(tmp_path):
    storage = LocalFileStorage(root=tmp_path)
    service = PDFService(storage)

    html = "<h1>Hello</h1><p>World</p>"
    rel_path = Path("test.pdf")
    pdf_path = service.html_to_pdf(html, rel_path)

    # Ensure file is written and non-empty
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 100  # minimal size 

def test_placeholder_renderer_bytes():
    """Directly exercise the static placeholder PDF renderer for coverage."""
    from backend.core.pdf_service import PDFService

    sample_html = "<h2>Hi</h2><p>There</p>"
    pdf_bytes = PDFService._render_placeholder_pdf(sample_html)

    # The helper should return non-empty bytes starting with PDF header
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 100  # minimal reasonable size 