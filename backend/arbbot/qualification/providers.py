"""Exchange boundaries for automatic evidence and public execution assumptions."""

from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol
from urllib.parse import urlsplit

from sqlalchemy import select

from arbbot.domain import utcnow
from arbbot.matching.classification_input import source_text
from arbbot.matching.contracts import EVENT_FIELDS
from arbbot.qualification.models import ContractEvidence
from arbbot.qualification.rules import parse_contract
from arbbot.sources.versions import latest_document
from arbbot.storage.models import SourceArtifactRecord
from arbbot.storage.repository import aware


class EvidenceProvider(Protocol):
    version: str

    async def resolve(self, session, market, max_age: int) -> ContractEvidence: ...


@dataclass(frozen=True)
class PublicEvidence:
    """Require exact adapter-captured instrument relationships and current documents."""

    hosts: tuple[str, ...]
    version: str = "public-evidence-v1"

    async def resolve(self, session, market, max_age):
        now = utcnow()
        definition, issues = parse_contract(market)
        issues = list(issues)
        details = market.settlement_details
        if details.get("source_status") != "captured":
            issues.append("applicable_sources_incomplete")
        issues.extend(details.get("source_issues", ()))
        refs = details.get("source_references", ())
        if not refs:
            issues.append("instrument_document_relationship_missing")
        rows = (
            await session.scalars(
                select(SourceArtifactRecord).where(
                    SourceArtifactRecord.market_key == f"{market.mode}:{market.id}",
                    SourceArtifactRecord.label.not_in(
                        ("fee_policy", "kalshi_event", "kalshi_series", "polymarket_us_market")
                    ),
                )
            )
        ).all()
        ids, deadlines = [], [now + timedelta(seconds=max_age), market.closes_at]
        captured_texts = []
        for url in sorted({row.url for row in rows}):
            current = await latest_document(session, market.mode, url)
            local = max(
                (row for row in rows if row.url == url),
                key=lambda row: (aware(row.last_seen_at), row.id),
            )
            if (
                not current
                or current.status != "captured"
                or current.content_digest != local.content_digest
                or aware(current.last_seen_at) + timedelta(seconds=max_age) <= now
            ):
                issues.append("document_unavailable_or_stale")
                continue
            # The adapter must establish applicability. Indexes and resolution
            # agency homepages alone cannot qualify a product specification.
            if not any(ref.get("url") == url for ref in refs):
                issues.append("document_relationship_missing")
            if urlsplit(url).hostname not in self.hosts:
                issues.append("unsupported_document_authority")
            derived = await source_text(local)
            if derived.status != "complete":
                issues.append("document_text_incomplete")
            else:
                text = "\n".join(page.text for page in derived.pages)
                captured_texts.append(text)
                # A new exception in a captured specification cannot be ignored
                # merely because all previously recognized quotes still exist.
                if local.label != "resolution_source":
                    document_market = market.model_copy(update={"rules": text})
                    document, document_issues = parse_contract(document_market)
                    if not document_issues:
                        for name in EVENT_FIELDS:
                            expected = definition.facts.get(name)
                            actual = document.facts.get(name)
                            if expected and actual and expected.value != actual.value:
                                issues.append("document_event_contradiction:" + name)
                    if document_issues or (
                        {k: f.value for k, f in document.facts.items()}
                        != {k: f.value for k, f in definition.facts.items()}
                    ):
                        issues.append("applicable_document_language_unmodeled")
            ids.append(local.id)
            deadlines.append(aware(current.last_seen_at) + timedelta(seconds=max_age))
        if not ids:
            issues.append("applicable_document_missing")
        facts = [
            *definition.facts.values(),
            *(p.evidence for p in definition.settlement_policies or ()),
        ]
        for fact in facts:
            if not any(fact.quote in text for text in captured_texts):
                issues.append("interpretation_not_in_captured_document")
        return ContractEvidence(
            definition=definition,
            artifact_ids=tuple(ids),
            blocked_reasons=tuple(sorted(set(issues))),
            expires_at=min(deadlines),
            provider_version=self.version,
        )


@dataclass(frozen=True)
class Capabilities:
    evidence: EvidenceProvider
    # Public calculation assumptions, not assertions about a particular account.
    fee_account_class: str | None = None
    legacy_execution_context: bool = False
    fee_refresh: object | None = None
    execution_version: str = "binary-usd-v1"
    source_hosts: tuple[str, ...] = ()

    def execution_issues(self, market):
        issues = []
        c, s = market.instrument_constraints, market.execution_semantics
        if c is None or s is None:
            return ("native_constraints_unavailable",)
        if c.unit_payout != 1 or market.settlement_asset != "USD":
            issues.append("unsupported_unit_payout_or_currency")
        if s.no_action == "short_instrument" and (
            not s.no_native_price_is_complement or s.gross_short_collateral_per_contract != 1
        ):
            issues.append("unsupported_short_collateral")
        return tuple(issues)


def capabilities(venue):
    from arbbot.venues import VENUES

    registration = VENUES.get(venue)
    return registration.capabilities if registration else None


def requires_context(markets):
    return any((cap := capabilities(m.venue)) and cap.legacy_execution_context for m in markets)


def is_short(market, side):
    return bool(
        side == "no"
        and market.execution_semantics
        and market.execution_semantics.no_action == "short_instrument"
    )


def native_price(market, side, price):
    return (
        1 - price
        if (
            side == "no"
            and market.execution_semantics
            and market.execution_semantics.no_native_price_is_complement
        )
        else price
    )


def registered_source_hosts():
    from arbbot.venues import VENUES

    return frozenset(
        host
        for entry in VENUES.values()
        if entry.capabilities
        for host in (
            *entry.capabilities.source_hosts,
            *getattr(entry.capabilities.evidence, "hosts", ()),
        )
    )
