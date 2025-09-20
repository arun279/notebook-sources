from __future__ import annotations

import requests

from backend.core.archive_resolver import ArchiveResolver, WAYBACK_AVAIL
from tests.unit.test_archive_resolver import _FakeResponse


def test_archive_resolver_aggressive_success(monkeypatch):
    """Aggressive mode returns success if a snapshot appears after polling."""
    # State to track whether the snapshot is available
    snapshot_available = {"value": False}

    def fake_get(url: str, *args, **kwargs):
        if url == WAYBACK_AVAIL:
            # First check fails, second succeeds
            has_snapshot = snapshot_available["value"]
            snapshot_available["value"] = True  # Flip state for next call
            return _FakeResponse(url, has_snapshot=has_snapshot)
        return _FakeResponse(url, has_snapshot=True)

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr("backend.core.archive_resolver.time.sleep", lambda _s: None)

    resolver = ArchiveResolver()
    outcome = resolver.resolve("https://becomes-available.com", aggressive=True)

    assert outcome.success is True
    assert outcome.source == "wayback"


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
