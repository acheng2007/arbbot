"""Shared quote eligibility rules for ingestion health and financial evaluation."""

from datetime import datetime, timedelta

from arbbot.domain import Book, Market


def book_issue(
    market: Market, book: Book | None, now: datetime, max_age_seconds: int
) -> str | None:
    if book is None:
        return "book_missing"
    if book.market_id != market.id:
        return "book_identity_mismatch"
    if book.mode != market.mode:
        return "book_mode_mismatch"
    if book.received_at > now + timedelta(seconds=2) or (
        book.source_at and book.source_at > now + timedelta(seconds=2)
    ):
        return "book_from_future"
    if now >= book.effective_at + timedelta(seconds=max_age_seconds):
        return "book_stale"
    return None
