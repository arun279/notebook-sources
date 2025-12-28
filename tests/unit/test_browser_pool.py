from __future__ import annotations

"""Tests for the browser pool module.

These tests focus on the pool lifecycle and edge cases that are difficult
to reach through integration tests.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio

from backend.core.browser_pool import AsyncBrowserPool


class TestBrowserPoolLifecycle:
    """Tests for pool startup and shutdown behavior."""

    @pytest.mark.asyncio
    @patch("backend.core.browser_pool.async_playwright")
    async def test_start_initializes_browsers(self, mock_async_playwright):
        """Pool start() launches the configured number of browser instances."""
        # Arrange
        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_async_playwright.return_value.start = AsyncMock(return_value=mock_playwright)

        pool = AsyncBrowserPool(size=3)

        # Act
        await pool.start()

        # Assert
        assert mock_playwright.chromium.launch.call_count == 3
        assert pool._started is True
        assert pool._available.qsize() == 3

    @pytest.mark.asyncio
    @patch("backend.core.browser_pool.async_playwright")
    async def test_start_is_idempotent(self, mock_async_playwright):
        """Calling start() multiple times only initializes once."""
        mock_playwright = MagicMock()
        mock_async_playwright.return_value.start = AsyncMock(return_value=mock_playwright)
        mock_playwright.chromium.launch = AsyncMock(return_value=MagicMock())

        pool = AsyncBrowserPool(size=2)

        # Act - call start twice
        await pool.start()
        await pool.start()

        # Assert - should only initialize once
        assert mock_playwright.chromium.launch.call_count == 2  # Only from first start

    @pytest.mark.asyncio
    @patch("backend.core.browser_pool.async_playwright")
    async def test_stop_closes_all_browsers(self, mock_async_playwright):
        """Pool stop() closes all browser instances and stops playwright."""
        mock_playwright = MagicMock()
        mock_browsers = [MagicMock() for _ in range(3)]
        for browser in mock_browsers:
            browser.close = AsyncMock()
        mock_playwright.chromium.launch = AsyncMock(side_effect=mock_browsers)
        mock_playwright.stop = AsyncMock()
        mock_async_playwright.return_value.start = AsyncMock(return_value=mock_playwright)

        pool = AsyncBrowserPool(size=3)
        await pool.start()

        # Act
        await pool.stop()

        # Assert
        for browser in mock_browsers:
            browser.close.assert_called_once()
        mock_playwright.stop.assert_called_once()
        assert pool._started is False

    @pytest.mark.asyncio
    @patch("backend.core.browser_pool.async_playwright")
    async def test_stop_is_idempotent(self, mock_async_playwright):
        """Calling stop() multiple times is safe."""
        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        mock_browser.close = AsyncMock()
        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_playwright.stop = AsyncMock()
        mock_async_playwright.return_value.start = AsyncMock(return_value=mock_playwright)

        pool = AsyncBrowserPool(size=1)
        await pool.start()

        # Act - call stop twice
        await pool.stop()
        await pool.stop()

        # Assert - should only call playwright.stop() once
        mock_playwright.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_before_start_is_noop(self):
        """Calling stop() on an unstarted pool does nothing."""
        pool = AsyncBrowserPool(size=2)

        # Act - should not raise
        await pool.stop()

        # Assert
        assert pool._started is False


class TestBrowserPoolAcquire:
    """Tests for browser acquisition and release."""

    @pytest.mark.asyncio
    @patch("backend.core.browser_pool.async_playwright")
    async def test_acquire_returns_browser(self, mock_async_playwright):
        """acquire() yields a browser from the pool."""
        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        mock_browser.new_page = AsyncMock()
        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_async_playwright.return_value.start = AsyncMock(return_value=mock_playwright)

        pool = AsyncBrowserPool(size=1)
        await pool.start()

        # Act
        async with pool.acquire() as browser:
            # Assert - got the browser
            assert browser is mock_browser
            # During acquisition, pool should be empty
            assert pool._available.qsize() == 0

        # After release, browser should be back in pool
        assert pool._available.qsize() == 1

    @pytest.mark.asyncio
    async def test_acquire_before_start_raises(self):
        """acquire() raises RuntimeError if pool not started."""
        pool = AsyncBrowserPool(size=1)

        # Act & Assert
        with pytest.raises(RuntimeError, match="Browser pool not started"):
            async with pool.acquire():
                pass

    @pytest.mark.asyncio
    @patch("backend.core.browser_pool.async_playwright")
    async def test_acquire_recovers_from_error(self, mock_async_playwright):
        """If an error occurs during browser use, pool recreates the browser."""
        mock_playwright = MagicMock()
        mock_browser_original = MagicMock()
        mock_browser_original.close = AsyncMock()
        mock_browser_replacement = MagicMock()
        mock_playwright.chromium.launch = AsyncMock(side_effect=[
            mock_browser_original,
            mock_browser_replacement,
        ])
        mock_async_playwright.return_value.start = AsyncMock(return_value=mock_playwright)

        pool = AsyncBrowserPool(size=1)
        await pool.start()

        # Act - simulate an error during browser use
        with pytest.raises(ValueError):
            async with pool.acquire() as browser:
                assert browser is mock_browser_original
                raise ValueError("Simulated browser error")

        # Assert - original browser was closed, replacement created
        mock_browser_original.close.assert_called_once()
        assert mock_playwright.chromium.launch.call_count == 2

        # Pool should still have one browser (the replacement)
        assert pool._available.qsize() == 1

    @pytest.mark.asyncio
    @patch("backend.core.browser_pool.async_playwright")
    async def test_acquire_handles_close_error_during_recovery(self, mock_async_playwright):
        """If closing failed browser raises, recovery still proceeds."""
        mock_playwright = MagicMock()
        mock_browser_original = MagicMock()
        mock_browser_original.close = AsyncMock(side_effect=Exception("Close failed"))
        mock_browser_replacement = MagicMock()
        mock_playwright.chromium.launch = AsyncMock(side_effect=[
            mock_browser_original,
            mock_browser_replacement,
        ])
        mock_async_playwright.return_value.start = AsyncMock(return_value=mock_playwright)

        pool = AsyncBrowserPool(size=1)
        await pool.start()

        # Act - simulate error, close also fails
        with pytest.raises(ValueError):
            async with pool.acquire() as browser:
                raise ValueError("Simulated error")

        # Assert - pool still functional with replacement browser
        assert pool._available.qsize() == 1


class TestBrowserPoolIntegration:
    """Integration-style tests using real pool behavior with mocked Playwright."""

    @pytest.mark.asyncio
    @patch("backend.core.browser_pool.async_playwright")
    async def test_multiple_sequential_acquisitions(self, mock_async_playwright):
        """Multiple sequential acquire/release cycles work correctly."""
        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_async_playwright.return_value.start = AsyncMock(return_value=mock_playwright)

        pool = AsyncBrowserPool(size=1)
        await pool.start()

        # Act - acquire and release multiple times
        for i in range(5):
            async with pool.acquire() as browser:
                assert browser is mock_browser

        # Assert - same browser reused, still in pool
        assert pool._available.qsize() == 1
        assert mock_playwright.chromium.launch.call_count == 1  # Only created once

    @pytest.mark.asyncio
    @patch("backend.core.browser_pool.async_playwright")
    async def test_stop_handles_browser_close_errors(self, mock_async_playwright):
        """stop() handles errors when closing individual browsers."""
        mock_playwright = MagicMock()
        mock_browsers = [MagicMock() for _ in range(3)]
        # Second browser fails to close
        mock_browsers[1].close = AsyncMock(side_effect=Exception("Browser crash"))
        for i in [0, 2]:
            mock_browsers[i].close = AsyncMock()
        mock_playwright.chromium.launch = AsyncMock(side_effect=mock_browsers)
        mock_playwright.stop = AsyncMock()
        mock_async_playwright.return_value.start = AsyncMock(return_value=mock_playwright)

        pool = AsyncBrowserPool(size=3)
        await pool.start()

        # Act - should not raise despite close error
        await pool.stop()

        # Assert - all browsers attempted to close
        for browser in mock_browsers:
            browser.close.assert_called_once()
        mock_playwright.stop.assert_called_once()

