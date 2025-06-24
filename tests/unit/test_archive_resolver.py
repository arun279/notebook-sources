from backend.core.archive_resolver import ArchiveResolver


def test_archive_resolver_stub():
    resolver = ArchiveResolver()
    outcome = resolver.resolve("https://example.com")
    assert not outcome.success
    assert outcome.reason == "not-implemented" 