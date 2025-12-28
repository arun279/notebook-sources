from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
from contextlib import asynccontextmanager

from pypdf import PdfReader

from backend.core.pdf_service import PDFService
from backend.infra.storage.local_fs import LocalFileStorage


@patch("backend.core.pdf_service.sync_playwright")
def test_playwright_renderer_happy_path(mock_sync_playwright, tmp_path):
    """Verify that the Playwright renderer is invoked when available (no pool)."""
    # Arrange: Mock the entire Playwright machinery
    mock_page = MagicMock()
    mock_browser = MagicMock()
    mock_playwright = MagicMock()
    mock_playwright.chromium.launch.return_value = mock_browser
    mock_browser.new_page.return_value = mock_page
    mock_sync_playwright.return_value.__enter__.return_value = mock_playwright

    # Arrange: Set up the service WITHOUT browser pool (fallback path)
    storage = LocalFileStorage(root=tmp_path)
    service = PDFService(storage, browser_pool=None)
    html = "<h1>Hello from Playwright</h1>"
    rel_path = Path("playwright.pdf")

    # Act: Call the PDF generation method
    with patch("backend.core.pdf_service._HAS_PLAYWRIGHT", True):
        service.html_to_pdf(html, rel_path)

    # Assert: Ensure the correct methods were called
    storage_root = storage.root
    expected_html_path = storage_root / rel_path.with_suffix(".html")
    assert expected_html_path.exists()

    mock_playwright.chromium.launch.assert_called_once()
    mock_browser.new_page.assert_called_once()
    mock_page.goto.assert_called_once_with(f"file://{expected_html_path}")
    mock_page.pdf.assert_called_once()
    mock_browser.close.assert_called_once()


def test_playwright_renderer_with_browser_pool(tmp_path):
    """Verify that PDFService uses browser pool when provided."""
    # Arrange: Create mock browser pool
    mock_page = MagicMock()
    mock_page.pdf = AsyncMock(return_value=b"%PDF-1.4 fake pdf content")
    mock_page.goto = AsyncMock()
    mock_page.close = AsyncMock()

    mock_browser = MagicMock()
    mock_browser.new_page = AsyncMock(return_value=mock_page)

    @asynccontextmanager
    async def mock_acquire():
        yield mock_browser

    mock_pool = MagicMock()
    mock_pool.acquire = mock_acquire

    # Arrange: Set up the service WITH browser pool
    storage = LocalFileStorage(root=tmp_path)
    service = PDFService(storage, browser_pool=mock_pool)
    html = "<h1>Hello from pooled browser</h1>"
    rel_path = Path("pooled.pdf")

    # Act
    with patch("backend.core.pdf_service._HAS_PLAYWRIGHT", True):
        pdf_path = service.html_to_pdf(html, rel_path)

    # Assert: Browser pool was used, page was created and closed
    mock_browser.new_page.assert_called_once()
    mock_page.goto.assert_called_once()
    mock_page.pdf.assert_called_once()
    mock_page.close.assert_called_once()  # Page closed, but NOT browser

    # Assert: PDF was saved
    assert pdf_path.exists()


def test_playwright_renderer_pool_closes_page_on_error(tmp_path):
    """Verify page.close() is called even when PDF generation fails."""
    # Arrange
    mock_page = MagicMock()
    mock_page.pdf = AsyncMock(side_effect=Exception("PDF generation failed"))
    mock_page.goto = AsyncMock()
    mock_page.close = AsyncMock()

    mock_browser = MagicMock()
    mock_browser.new_page = AsyncMock(return_value=mock_page)

    @asynccontextmanager
    async def mock_acquire():
        yield mock_browser

    mock_pool = MagicMock()
    mock_pool.acquire = mock_acquire

    storage = LocalFileStorage(root=tmp_path)
    service = PDFService(storage, browser_pool=mock_pool)
    html = "<h1>This will fail</h1>"
    rel_path = Path("error.pdf")

    # Act & Assert - should fall back to FPDF, page still closed
    with patch("backend.core.pdf_service._HAS_PLAYWRIGHT", True):
        # The exception is caught and falls back to FPDF
        pdf_path = service.html_to_pdf(html, rel_path)

    # Page should be closed in the finally block
    mock_page.close.assert_called_once()
    # Fallback PDF should exist
    assert pdf_path.exists()


@patch("backend.core.pdf_service.sync_playwright")
def test_playwright_fallback_to_fpdf_on_error(mock_sync_playwright, tmp_path):
    """Verify fallback to the placeholder renderer if Playwright fails."""
    # Arrange: Mock Playwright to raise an exception
    mock_sync_playwright.side_effect = Exception("Playwright error")

    # Arrange: Set up the service and inputs
    storage = LocalFileStorage(root=tmp_path)
    service = PDFService(storage)
    html = "<h1>Fallback content</h1>"
    rel_path = Path("fallback.pdf")

    # Act: Call the PDF generation method
    with patch("backend.core.pdf_service._HAS_PLAYWRIGHT", True):
        pdf_path = service.html_to_pdf(html, rel_path)

    # Assert: Ensure the placeholder PDF was created
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 100
    # Verify it contains the fallback content
    with open(pdf_path, "rb") as f:
        reader = PdfReader(f)
        page = reader.pages[0]
        text = page.extract_text()
    assert "Fallback content" in text

def test_placeholder_renderer_string_return():
    """Verify the placeholder renderer handles FPDF's string output."""
    # Arrange: Mock FPDF.output to return a string
    with patch("backend.core.pdf_service.FPDF") as mock_fpdf_class:
        mock_pdf_instance = MagicMock()
        # FPDF returns a latin-1 encoded string in some cases
        mock_pdf_instance.output.return_value = "pdf_content_string"
        mock_fpdf_class.return_value = mock_pdf_instance

        # Act
        pdf_bytes = PDFService._render_placeholder_pdf("html")

        # Assert
        assert isinstance(pdf_bytes, bytes)
        assert pdf_bytes == "pdf_content_string".encode("latin1")

