"""Retrieve immutable live fee snapshots independently of quotes and calculation."""

from datetime import datetime, timedelta
from decimal import Decimal
from urllib.parse import quote

from arbbot.domain import digest, utcnow
from arbbot.execution.models import Citation, ConfigurationWrite, ExecutableFeePolicy
from arbbot.execution.repository import ExecutionRepository
from arbbot.reviews.models import Actor
from arbbot.sources.models import SourceCapture
from arbbot.sources.repository import SourceRepository
from arbbot.sources.text import derive_text

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
        if not access or access.value.status != "verified" or access.value.expires_at <= utcnow():
            return
        permissions = {p.venue: p for p in access.value.permissions}
        counts = {}
        for market in markets:
            if counts.get(market.venue, 0) >= self.settings.discovery_limit:
                continue
            permission = permissions.get(market.venue)
            if permission is None or market.id not in permission.market_ids:
                continue
            counts[market.venue] = counts.get(market.venue, 0) + 1
            now, metadata = utcnow(), {}
            if market.venue == "polymarket_us":
                url = "https://docs.polymarket.us/fees"
                coefficient = Decimal("0.10")  # Upper bound for standard and Table Tennis.
                expiry, effective = now + timedelta(minutes=5), US_EFFECTIVE
                formula, increment, precision = "us_standard", None, None
            elif market.venue == "kalshi":
                http = self.adapters["kalshi"].http
                raw = (await http.get(BASE + "/markets/" + quote(market.external_id, safe="")))[
                    "market"
                ]
                event = (await http.get(BASE + "/events/" + quote(raw["event_ticker"], safe="")))[
                    "event"
                ]
                series = (
                    await http.get(BASE + "/series/" + quote(event["series_ticker"], safe=""))
                )["series"]
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
                continue
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
