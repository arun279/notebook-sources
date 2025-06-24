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


@dataclass(slots=True)
class ArchiveOutcome:
    success: bool
    archive_url: Optional[str] = None
    html: Optional[str] = None
    source: Optional[str] = None
    timestamp: Optional[datetime] = None
    reason: Optional[str] = None


class ArchiveResolver:  # noqa: WPS110 – domain term
    """Resolve archived snapshots for a URL (stub impl)."""

    def resolve(self, url: str, paywalled: bool = False, aggressive: bool = False) -> ArchiveOutcome:  # noqa: D401,E501
        # For now, always indicate failure so the caller can fall back to live URL.
        return ArchiveOutcome(success=False, reason="not-implemented") 