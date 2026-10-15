"""Retrieve immutable live fee snapshots independently of quotes and calculation."""

import asyncio
import logging
import re
from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from urllib.parse import quote

from arbbot.domain import digest, utcnow
from arbbot.execution.models import (
    Citation,
    ConfigurationWrite,
    ExecutableFeePolicy,
    UnavailableFeePolicy,
)
from arbbot.execution.repository import ExecutionRepository
from arbbot.reviews.models import Actor
from arbbot.sources.models import SourceCapture
from arbbot.sources.repository import SourceRepository
from arbbot.sources.text import derive_text

logger = logging.getLogger(__name__)

BASE = "https://external-api.kalshi.com/trade-api/v2"
US_EFFECTIVE = datetime.fromisoformat("2026-10-07T14:00:00+00:00")
ACTOR = Actor(issuer="official-policy-refresh", subject="public-fee-schedules")


def kalshi_parameters(metadata, now):
    market, event, series = (metadata[k] for k in ("market", "event", "series"))
    if (
        market["event_ticker"] != event["event_ticker"]
        or event["series_ticker"] != series["ticker"]
    ):
        raise ValueError("Fee identities mismatch")
    if market.get("market_type") != "binary" or Decimal(market["notional_value_dollars"]) != 1:
        raise ValueError("Unsupported fee instrument")
    for key in ("fee_type", "fee_multiplier", "fee_type_override", "fee_multiplier_override"):
        if market.get(key) is not None:
            raise ValueError("Unsupported market fee override")
    fee_type, multiplier = series["fee_type"], series["fee_multiplier"]
    expiry = now + timedelta(minutes=5)
    changes = metadata["event_changes"]
    if not isinstance(changes, list) or not isinstance(metadata["series_changes"], list):
        raise ValueError("Complete scheduled fee metadata required")
    applied = []
    for change in changes:
        if change["event_ticker"] != event["event_ticker"]:
            raise ValueError("Event fee-change identity mismatch")
        instant = datetime.fromisoformat(change["scheduled_ts"].replace("Z", "+00:00"))
        if instant > now:
            expiry = min(expiry, instant)
        else:
            applied.append((instant, change))
    if applied:
        latest_at = max(instant for instant, _ in applied)
        latest = [change for instant, change in applied if instant == latest_at]
        if len({digest(change) for change in latest}) > 1:
            raise ValueError("Conflicting simultaneous event fee changes")
        current = latest[0]
        fee_type = current["fee_type_override"] or fee_type
        multiplier = (
            current["fee_multiplier_override"]
            if (current["fee_multiplier_override"] is not None)
            else multiplier
        )
    elif (
        event.get("fee_type_override") is not None
        or event.get("fee_multiplier_override") is not None
    ):
        raise ValueError("Current override absent from complete event history")
    for change in metadata["series_changes"]:
        if change["series_ticker"] != series["ticker"]:
            raise ValueError("Series fee-change identity mismatch")
        instant = datetime.fromisoformat(change["scheduled_ts"].replace("Z", "+00:00"))
        if instant > now:
            expiry = min(expiry, instant)
    if fee_type not in ("quadratic", "quadratic_with_maker_fees"):
        raise ValueError("Unsupported fee model")
    if isinstance(multiplier, (bool, float)):
        raise ValueError("Fee multipliers require exact decimal metadata")
    coefficient = Decimal("0.07") * Decimal(multiplier)
    if not coefficient.is_finite() or coefficient < 0:
        raise ValueError("Invalid fee multiplier")
    return coefficient, expiry


def documented_general_rate(body):
    general = body  # The first labeled formula is general taker pricing, before maker pricing.
    match = re.search(
        r"fees\s*=\s*round\s+up\s*\(\s*M\s*[x×]\s*([0-9.]+)\s*[x×]\s*C\s*[x×]\s*P\s*[x×]\s*\(\s*1\s*-\s*P\s*\)",
        general,
    )
    return Decimal(match.group(1)) if match else None


class FeePolicyError(ValueError):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


class FeeRefresh:
    def __init__(self, settings, repository, adapters, fetcher):
        self.settings, self.repository = settings, repository
        self.adapters = {a.venue: a for a in adapters}
        self.fetcher = fetcher
        self.sources = SourceRepository(repository.database)
        self.configuration = ExecutionRepository(repository.database)

    async def refresh(self, markets):
        # Only approved installation products need fee work; bounded by monitoring budget.
        async with self.repository.database.sessions() as session:
            access = await self.configuration.current(session, "live:access:installation")
        from arbbot.qualification.providers import capabilities

        if self.settings.automatic_qualification:
            permissions = {
                venue: SimpleNamespace(
                    venue=venue,
                    market_ids=tuple(m.id for m in markets if m.venue == venue),
                    fee_account_class=cap.fee_account_class,
                )
                for venue in self.adapters
                if (cap := capabilities(venue)) and cap.fee_account_class
            }
        elif access and access.value.status == "verified" and access.value.expires_at > utcnow():
            permissions = {p.venue: p for p in access.value.permissions}
        else:
            return
        selected = []
        from arbbot.storage.models import DiscoveryProgressRecord

        for venue, permission in permissions.items():
            eligible = sorted(
                (m for m in markets if m.venue == venue and m.id in permission.market_ids),
                key=lambda m: m.id,
            )
            key = f"live:fee-rotation:{venue}"
            async with self.repository.database.sessions.begin() as session:
                progress = await session.get(DiscoveryProgressRecord, key, with_for_update=True)
                offset = (progress.payload.get("offset", 0) if progress else 0) % max(
                    1, len(eligible)
                )
                cohort = (eligible[offset:] + eligible[:offset])[
                    : self.settings.monitoring_limit(venue)
                ]
                await session.merge(
                    DiscoveryProgressRecord(
                        key=key, mode="live", venue=venue, payload={"offset": offset + len(cohort)}
                    )
                )
                selected.extend((market, permission) for market in cohort)
        semaphore = asyncio.Semaphore(4)

        async def refresh_one(market, permission):
            async with semaphore:
                try:
                    cap = capabilities(market.venue)
                    if cap and cap.fee_refresh:
                        await cap.fee_refresh(self, market, permission)
                    else:
                        await self._refresh_market(market, permission)
                except Exception as exc:
                    logger.warning(
                        "fee_refresh_unavailable",
                        extra={"venue": market.venue, "error": type(exc).__name__},
                    )
                    async with self.repository.database.sessions() as session:
                        current = await self.configuration.current(
                            session, f"live:fees:{market.id}"
                        )
                    await self.configuration.save(
                        "live",
                        ConfigurationWrite(
                            expected_revision_id=current.id if current else None,
                            value=UnavailableFeePolicy(
                                market_id=market.id,
                                terms_hash=market.terms_hash,
                                reason=exc.reason
                                if isinstance(exc, FeePolicyError)
                                else (
                                    "unsupported_policy"
                                    if isinstance(exc, ValueError)
                                    else "provider_error"
                                ),
                                expires_at=utcnow() + timedelta(minutes=5),
                            ),
                            reason=(
                                "Withdraw unavailable public fee policy; no cost-envelope fallback"
                            ),
                        ),
                        ACTOR,
                    )

        await asyncio.gather(*(refresh_one(market, permission) for market, permission in selected))

    async def _refresh_market(self, market, permission):
        now, metadata = utcnow(), {}
        if market.venue == "polymarket_us":
            url = "https://docs.polymarket.us/fees"
            coefficient = Decimal("0.10")  # Upper bound for standard and Table Tennis.
            expiry, effective = now + timedelta(minutes=5), US_EFFECTIVE
            formula, increment, precision = "us_standard", None, None
        elif market.venue == "kalshi":
            if permission.fee_account_class != "direct":
                raise FeePolicyError("unverified_account_fees")
            http = self.adapters["kalshi"].http
            raw = (await http.get(BASE + "/markets/" + quote(market.external_id, safe="")))[
                "market"
            ]
            event = (await http.get(BASE + "/events/" + quote(raw["event_ticker"], safe="")))[
                "event"
            ]
            series = (await http.get(BASE + "/series/" + quote(event["series_ticker"], safe="")))[
                "series"
            ]
            changes, cursor, seen = [], "", set()
            for _ in range(10):
                page = await http.get(
                    BASE + "/events/fee_changes",
                    params={
                        "event_ticker": event["event_ticker"],
                        "limit": 1000,
                        "cursor": cursor,
                    },
                )
                changes.extend(page["event_fee_changes"])
                cursor = page["cursor"]
                if not cursor:
                    break
                if cursor in seen:
                    raise ValueError("Fee pagination repeated")
                seen.add(cursor)
            else:
                raise ValueError("Fee pagination incomplete")
            scheduled = await http.get(
                BASE + "/series/fee_changes",
                params={"series_ticker": series["ticker"], "show_historical": "false"},
            )
            metadata = {
                "market": raw,
                "event": event,
                "series": series,
                "event_changes": changes,
                "series_changes": scheduled["series_fee_change_arr"],
            }
            coefficient, expiry = kalshi_parameters(metadata, now)
            effective = now
            url = "https://docs.kalshi.com/getting_started/fee_rounding"
            formula, increment = "kalshi_quadratic", Decimal("0.01")
            precision = "0.0001" if permission.fee_account_class == "direct" else "0.01"
        else:
            raise ValueError("Unsupported fee venue")
        content, media_type, retrieved_at = await self.fetcher.read(url)
        expiry = min(expiry, retrieved_at + timedelta(minutes=5))
        artifact = await self.sources.record(
            SourceCapture(
                mode="live",
                market_id=market.id,
                venue=market.venue,
                url=url,
                label="fee_policy",
                content=content,
                content_type=media_type,
                retrieved_at=retrieved_at,
            )
        )
        text = await derive_text(content, media_type, artifact.id)
        body = "\n".join(page.text for page in text.pages)
        if text.status != "complete":
            raise ValueError("Fee documentation extraction incomplete")
        if market.venue == "polymarket_us":
            required = ("October 7, 2026", "0.0695", "0.10", "cumulative exact fee")
            if not all(part in body for part in required):
                raise ValueError("US fee schedule changed or unsupported")
        quotation = next((page.text[:8000] for page in text.pages if page.text), "")
        supporting_sources = []
        if market.venue == "kalshi":
            url = "https://kalshi.com/docs/kalshi-fee-schedule.pdf"
            content, media_type, receipt = await self.fetcher.read(url)
            formula_capture = await self.sources.record(
                SourceCapture(
                    mode="live",
                    market_id=market.id,
                    venue=market.venue,
                    url=url,
                    label="fee_policy",
                    content=content,
                    content_type=media_type,
                    retrieved_at=receipt,
                )
            )
            formula_text = await derive_text(content, media_type, formula_capture.id)
            body = "\n".join(page.text for page in formula_text.pages)
            if (
                formula_text.status != "complete"
                or documented_general_rate(body) != Decimal("0.07")
                or "Trading Fees" not in " ".join(body.split())
            ):
                raise FeePolicyError("unsupported_policy")
            supporting_sources.append(
                Citation(
                    artifact_id=formula_capture.id,
                    content_hash=formula_capture.content_digest,
                    quotation=next(
                        page.text[:8000] for page in formula_text.pages if "0.07" in page.text
                    ),
                )
            )
            expiry = min(expiry, receipt + timedelta(minutes=5))
        policy = ExecutableFeePolicy(
            market_id=market.id,
            venue=market.venue,
            terms_hash=market.terms_hash,
            formula=formula,
            coefficient=coefficient,
            minimum_execution_quantity=increment,
            balance_precision=precision,
            account_class=permission.fee_account_class,
            source=Citation(
                artifact_id=artifact.id,
                content_hash=artifact.content_digest,
                quotation=quotation,
            ),
            supporting_sources=tuple(supporting_sources),
            metadata_hash=digest(metadata),
            metadata=metadata,
            observed_at=now,
            effective_at=effective,
            expires_at=expiry,
        )
        async with self.repository.database.sessions() as session:
            current = await self.configuration.current(session, f"live:fees:{market.id}")
        await self.configuration.save(
            "live",
            ConfigurationWrite(
                expected_revision_id=current.id if current else None,
                value=policy,
                reason=(
                    "Refresh documented conservative taker policy without rebates or discounts"
                ),
            ),
            ACTOR,
        )
