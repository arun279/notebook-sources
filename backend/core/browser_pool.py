from __future__ import annotations

"""Async browser pool for Playwright async API.

This module provides a pool of reusable Chromium browser instances to avoid
the significant overhead of launching/closing browsers for each PDF generation.
With pooling, browser startup cost is amortized across all PDF renders.
"""

from playwright.async_api import async_playwright, Browser, Playwright
import asyncio
from contextlib import asynccontextmanager
import logging

logger = logging.getLogger(__name__)


class AsyncBrowserPool:
    """Async browser pool for reusable Chromium browser instances.

    Usage:
        pool = AsyncBrowserPool(size=4)
        await pool.start()

        async with pool.acquire() as browser:
            page = await browser.new_page()
            # ... use page
            await page.close()

        await pool.stop()
    """

    def __init__(self, size: int = 4) -> None:
        """Initialize the browser pool.

        Args:
            size: Number of browser instances to maintain in the pool.
        """
        self._size = size
        self._playwright: Playwright | None = None
        self._browsers: list[Browser] = []
        self._available: asyncio.Queue[Browser] = asyncio.Queue()
        self._lock = asyncio.Lock()
        self._started = False

    async def start(self) -> None:
        """Initialize playwright and launch browser instances.

        This should be called once at application startup. Subsequent calls
        are no-ops if the pool is already started.
        """
        async with self._lock:
            if self._started:
                logger.warning("Browser pool already started, ignoring start() call")
                return

            logger.info(f"Starting browser pool with {self._size} instances...")
            self._playwright = await async_playwright().start()

            for i in range(self._size):
                try:
                    browser = await self._playwright.chromium.launch(args=["--no-sandbox"])
                    self._browsers.append(browser)
                    await self._available.put(browser)
                    logger.info(f"Browser pool: launched instance {i + 1}/{self._size}")
                except Exception as e:
                    logger.error(f"Failed to launch browser instance {i + 1}: {e}")
                    raise

            self._started = True
            logger.info("Browser pool startup complete")

    async def stop(self) -> None:
        """Close all browsers and stop playwright.

        This should be called once at application shutdown. Subsequent calls
        are no-ops if the pool is already stopped.
        """
        async with self._lock:
            if not self._started:
                return

            logger.info("Shutting down browser pool...")
            closed = 0

            for browser in self._browsers:
                try:
                    await browser.close()
                    closed += 1
                except Exception as e:
                    logger.warning(f"Error closing browser: {e}")

            if self._playwright:
                try:
                    await self._playwright.stop()
                except Exception as e:
                    logger.warning(f"Error stopping playwright: {e}")

            self._browsers.clear()
            self._started = False
            logger.info(f"Browser pool: closed {closed} instances")

    @asynccontextmanager
    async def acquire(self):
        """Acquire a browser from the pool. Blocks until one is available.

        If the browser encounters an error during use, it will be automatically
        replaced with a new instance to keep the pool healthy.

        Yields:
            Browser: A Chromium browser instance from the pool.

        Raises:
            Exception: Re-raises any exception that occurred during browser use.
        """
        if not self._started:
            raise RuntimeError("Browser pool not started. Call start() first.")

        browser = await self._available.get()  # Blocks if pool exhausted
        try:
            yield browser
        except Exception as e:
            # Browser might be in bad state - recreate it
            logger.warning(f"Browser error during use, recreating instance: {e}")
            try:
                await browser.close()
            except Exception as close_err:
                logger.debug(f"Error closing failed browser: {close_err}")

            # Create a replacement browser
            if self._playwright:
                try:
                    browser = await self._playwright.chromium.launch(args=["--no-sandbox"])
                    logger.info("Successfully recreated browser instance")
                except Exception as launch_err:
                    logger.error(f"Failed to recreate browser: {launch_err}")
                    # Put a None or raise? For now, try to put back what we have

            await self._available.put(browser)
            raise  # Re-raise the original exception
        else:
            # Normal case - return browser to pool
            await self._available.put(browser)

