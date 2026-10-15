"""Derived quotations stay bounded and retain their immutable source identity."""

import pytest

from arbbot.sources.text import MAX_TEXT, derive_text


async def test_html_text_excludes_executable_content_and_preserves_provenance():
    result = await derive_text(
        b"<h1>Terms</h1><script>ignore()</script><p>Cancellation pays half.</p>",
        "text/html",
        "artifact-123",
    )
    assert result.status == "complete"
    assert "Cancellation pays half." in result.pages[0].text
    assert "ignore" not in result.pages[0].text
    assert result.artifact_id == "artifact-123"
    assert len(result.content_digest) == len(result.text_digest) == 64


async def test_text_limit_is_explicit():
    result = await derive_text(b"a" * (MAX_TEXT + 1), "text/plain", "long")
    assert result.status == "partial"
    assert result.reason == "extraction_limit_reached"
    assert len(result.pages[0].text) == MAX_TEXT


@pytest.mark.parametrize(
    "content,media_type",
    [
        (b"%PDF-1.4\ninvalid\n%%EOF", "application/pdf"),
        (b"\xff", "text/plain"),
        (b"", "text/plain"),
        (b"binary", "application/octet-stream"),
    ],
)
async def test_failed_extraction_never_claims_complete(content, media_type):
    result = await derive_text(content, media_type, "bad")
    assert result.status == "unavailable"
    assert result.reason and not result.pages


async def test_extractor_timeout_is_bounded_and_explicit():
    result = await derive_text(b"Terms", "text/plain", "slow", limit_seconds=0.001)
    assert result.status == "unavailable" and result.reason == "extraction_timeout"
