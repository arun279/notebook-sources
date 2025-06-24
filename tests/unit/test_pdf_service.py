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