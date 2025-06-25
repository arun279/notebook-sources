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


def test_archive_resolver_aggressive_timeout(monkeypatch):
    """Aggressive mode returns a *timeout* failure when no snapshot becomes available."""

    # Stub requests.get to always report *no snapshot* and accept save requests.
    def fake_get(url: str, *args, **kwargs):  # noqa: D401
        return _FakeResponse(url, has_snapshot=False)

    monkeypatch.setattr(requests, "get", fake_get)

    # Speed-up loop inside aggressive mode – skip real sleep and elapse time quickly.
    monkeypatch.setattr("backend.core.archive_resolver.time.sleep", lambda _s: None)

    # Controlled time progress: first call = 0, then +61 seconds each invocation.
    ticks = {"now": 0}

    def fake_time():  # noqa: D401
        ticks["now"] += 61
        return ticks["now"]

    monkeypatch.setattr("backend.core.archive_resolver.time.time", fake_time)

    resolver = ArchiveResolver()
    outcome = resolver.resolve("https://timeout.com", aggressive=True)

    assert outcome.success is False
    assert outcome.reason == "wayback-save-timeout" 