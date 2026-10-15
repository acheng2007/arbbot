"""Mode-scoped document generations using immutable bytes and durable receipt metadata."""

from sqlalchemy import select, text

from arbbot.domain import digest
from arbbot.storage.models import MarketRecord, SourceArtifactRecord


async def lock_document(session, mode, url):
    if session.get_bind().dialect.name == "postgresql":
        key = int(digest(["arbbot-document", mode, url])[:16], 16)
        if key >= 2**63:
            key -= 2**64
        await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})


async def latest_document(session, mode, url):
    return await session.scalar(
        select(SourceArtifactRecord)
        .join(MarketRecord, MarketRecord.key == SourceArtifactRecord.market_key)
        .where(MarketRecord.mode == mode, SourceArtifactRecord.url == url)
        .order_by(SourceArtifactRecord.last_seen_at.desc(), SourceArtifactRecord.id.desc())
        .limit(1)
    )


async def bound_versions(session, mode, artifact_ids, *, lock=False):
    if not artifact_ids:
        return {}
    rows = (
        await session.scalars(
            select(SourceArtifactRecord).where(SourceArtifactRecord.id.in_(artifact_ids))
        )
    ).all()
    versions = {}
    for url in sorted({row.url for row in rows}):
        if lock:
            await lock_document(session, mode, url)
        current = await latest_document(session, mode, url)
        versions[url] = current.details.get("source_generation", 0) if current else 0
    return versions
