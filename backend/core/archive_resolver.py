from __future__ import annotations

"""Archive resolver stub.

The MVP spec describes a multi-stage strategy for retrieving archived snapshots
when a reference appears paywalled.  Implementing that entire algorithm would
require external APIs and rate-limiting; for *MVP code completeness* the
present class only exposes the contract so that the scraper can call it and
proceed regardless of paywall status.  A future enhancement can replace the
body of :pymeth:`resolve` without touching call-sites.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import json
import time
import requests


@dataclass(slots=True)
class ArchiveOutcome:
    success: bool
    archive_url: Optional[str] = None
    html: Optional[str] = None
    source: Optional[str] = None
    timestamp: Optional[datetime] = None
    reason: Optional[str] = None


WAYBACK_AVAIL = "https://archive.org/wayback/available"


class ArchiveResolver:  # noqa: WPS110 – domain term
    """Resolve archived snapshots for a URL (Wayback-first strategy – MVP).

    The implementation focuses on the *primary* path described in the project
    plan (Wayback Machine).  It keeps the interface identical so that a future
    enhancement can extend the fall-back chain (archive.today, Memento, etc.)
    without touching call-sites.
    """

    def resolve(  # noqa: D401,E501
        self, url: str, paywalled: bool = False, aggressive: bool = False, timeout: int = 30
    ) -> ArchiveOutcome:
        """Attempt to fetch a snapshot HTML for *url*.

        When ``aggressive`` is True and no snapshot is found, the resolver will
        trigger a save request and poll Wayback for up to 2 minutes.
        """
        try:
            outcome = self._check_availability(url, timeout)
            if outcome.success or not aggressive:
                return outcome

            # Aggressive mode – ask Wayback to save then poll.
            save_url = f"https://web.archive.org/save/{url}"
            requests.get(save_url, timeout=timeout)  # fire-and-forget trigger
            deadline = time.time() + 120  # 2 min budget
            while time.time() < deadline:
                time.sleep(15)
                outcome = self._check_availability(url, timeout)
                if outcome.success:
                    return outcome
            return ArchiveOutcome(success=False, reason="wayback-save-timeout")
        except Exception as exc:  # noqa: WPS429 – broad except to shield callers
            return ArchiveOutcome(success=False, reason=str(exc))

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    @staticmethod
    def _check_availability(url: str, timeout: int) -> ArchiveOutcome:  # noqa: D401
        resp = requests.get(WAYBACK_AVAIL, params={"url": url}, timeout=timeout)
        resp.raise_for_status()
        data: dict = resp.json()
        closest = data.get("archived_snapshots", {}).get("closest")
        if not closest:
            return ArchiveOutcome(success=False, reason="no-snapshot")

        archive_url = closest.get("url")
        ts = closest.get("timestamp")
        html_resp = requests.get(archive_url, timeout=timeout)
        html_resp.raise_for_status()
        return ArchiveOutcome(
            success=True,
            archive_url=archive_url,
            html=html_resp.text,
            source="wayback",
            timestamp=None if ts is None else datetime.strptime(ts, "%Y%m%d%H%M%S"),
        ) 