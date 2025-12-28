from __future__ import annotations

import requests

from backend.core.archive_resolver import ArchiveResolver, WAYBACK_AVAIL
from tests.unit.test_archive_resolver import _FakeResponse


def test_archive_resolver_aggressive_with_existing_snapshot(monkeypatch):
    """Aggressive mode returns success immediately if a snapshot already exists."""

    def fake_get(url: str, *args, **kwargs):
        if url == WAYBACK_AVAIL:
            return _FakeResponse(url, has_snapshot=True)
        return _FakeResponse(url, has_snapshot=True)

    monkeypatch.setattr(requests, "get", fake_get)

    resolver = ArchiveResolver()
    # Even with aggressive=True, if snapshot exists, return it directly
    outcome = resolver.resolve("https://has-snapshot.com", aggressive=True)

    assert outcome.success is True
    assert outcome.source == "wayback"
    assert outcome.retry_after is None  # No retry needed when successful


def test_archive_resolver_general_exception(monkeypatch):
    """A broad exception during resolution should result in a failure outcome."""

    def fake_get(*args, **kwargs):
        raise ConnectionError("Network is down")

    monkeypatch.setattr(requests, "get", fake_get)

    resolver = ArchiveResolver()
    outcome = resolver.resolve("https://any-url.com")

    assert outcome.success is False
    assert "Network is down" in str(outcome.reason)


def test_archive_resolver_no_timestamp(monkeypatch):
    """Absence of a timestamp in the Wayback response should not cause an error."""

    class _FakeResponseNoTimestamp(_FakeResponse):
        def json(self) -> dict:
            data = super().json()
            # Mutate the response to remove the timestamp
            if "closest" in data.get("archived_snapshots", {}):
                del data["archived_snapshots"]["closest"]["timestamp"]
            return data

    def fake_get(url: str, *args, **kwargs):
        if url == WAYBACK_AVAIL:
            return _FakeResponseNoTimestamp(url, has_snapshot=True)
        return _FakeResponse(url, has_snapshot=True)

    monkeypatch.setattr(requests, "get", fake_get)

    resolver = ArchiveResolver()
    outcome = resolver.resolve("https://no-timestamp.com")

    assert outcome.success is True
    assert outcome.timestamp is None
