from __future__ import annotations

import requests

from backend.core.archive_resolver import ArchiveResolver, WAYBACK_AVAIL


class _FakeResponse:  # Minimal stand-in for :class:`requests.Response`
    """Stub that mimics the subset of the *requests* API used by ArchiveResolver."""

    def __init__(self, url: str, *, has_snapshot: bool) -> None:  # noqa: D401
        self._url = url
        self._has_snapshot = has_snapshot

    # ---------------- requests.Response interface ----------------
    def raise_for_status(self) -> None:  # noqa: D401 – noop (always 200)
        return None

    def json(self) -> dict:  # noqa: D401 – only called for WAYBACK availability endpoint
        assert self._url == WAYBACK_AVAIL  # guard against accidental misuse
        if not self._has_snapshot:
            return {"archived_snapshots": {}}
        return {
            "archived_snapshots": {
                "closest": {
                    "url": "http://web.archive.org/web/20200101000000/https://example.com/",
                    "timestamp": "20200101000000",
                }
            }
        }

    # For the snapshot HTML fetch – `.text` attribute is accessed directly.
    @property
    def text(self) -> str:  # noqa: D401
        return "<html>cached version</html>"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_archive_resolver_success(monkeypatch):
    """Resolver returns *success* when Wayback has a snapshot available."""

    def fake_get(url: str, *args, **kwargs):  # noqa: D401
        if url == WAYBACK_AVAIL:
            return _FakeResponse(url, has_snapshot=True)
        # Second call fetches the actual archived HTML
        return _FakeResponse(url, has_snapshot=True)

    monkeypatch.setattr(requests, "get", fake_get)

    resolver = ArchiveResolver()
    outcome = resolver.resolve("https://example.com")

    assert outcome.success is True
    assert outcome.source == "wayback"
    assert outcome.archive_url and outcome.archive_url.startswith("http://web.archive.org/")
    assert outcome.html == "<html>cached version</html>"


def test_archive_resolver_no_snapshot(monkeypatch):
    """Resolver returns *failure* when Wayback has no snapshot available."""

    def fake_get(url: str, *args, **kwargs):  # noqa: D401
        # Always respond with *no snapshot*
        return _FakeResponse(url, has_snapshot=False)

    monkeypatch.setattr(requests, "get", fake_get)

    resolver = ArchiveResolver()
    outcome = resolver.resolve("https://no-snapshot.com")

    assert outcome.success is False
    assert outcome.reason == "no-snapshot"


def test_archive_resolver_aggressive_triggers_save(monkeypatch):
    """Aggressive mode triggers a save request and returns immediately without blocking."""
    save_triggered = {"called": False}

    def fake_get(url: str, *args, **kwargs):  # noqa: D401
        # Track if save endpoint was called
        if url.startswith("https://web.archive.org/save/"):
            save_triggered["called"] = True
            return _FakeResponse(WAYBACK_AVAIL, has_snapshot=False)
        return _FakeResponse(url, has_snapshot=False)

    monkeypatch.setattr(requests, "get", fake_get)

    resolver = ArchiveResolver()
    outcome = resolver.resolve("https://no-snapshot.com", aggressive=True)

    # Should return immediately with save-triggered reason
    assert outcome.success is False
    assert outcome.reason == "wayback-save-triggered"
    assert outcome.retry_after is not None
    assert save_triggered["called"]


def test_archive_resolver_aggressive_save_error_ignored(monkeypatch):
    """Aggressive mode ignores errors when triggering the save request."""
    call_count = {"value": 0}

    def fake_get(url: str, *args, **kwargs):  # noqa: D401
        call_count["value"] += 1
        if url.startswith("https://web.archive.org/save/"):
            raise ConnectionError("Save endpoint unavailable")
        return _FakeResponse(url, has_snapshot=False)

    monkeypatch.setattr(requests, "get", fake_get)

    resolver = ArchiveResolver()
    outcome = resolver.resolve("https://test.com", aggressive=True)

    # Should still return save-triggered even if save request failed
    assert outcome.success is False
    assert outcome.reason == "wayback-save-triggered"
    assert outcome.retry_after is not None 