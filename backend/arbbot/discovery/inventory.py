"""Durable bounded page scanning independent of the quote-monitoring budget."""

from datetime import datetime, timedelta
from urllib.parse import quote

from sqlalchemy import select

from arbbot.discovery.models import DiscoveryDecision, DiscoveryScan
from arbbot.domain import digest, restore, utcnow
from arbbot.exchanges.discovery import candidate
from arbbot.storage.models import (
    CatalogInventoryRecord,
    CatalogObservationRecord,
    DiscoveryProgressRecord,
    MarketRecord,
)


class CatalogInventory:
    def __init__(self, settings, repository):
        self.settings, self.repository = settings, repository

    async def progress(self, venue):
        async with self.repository.database.sessions() as session:
            row = await session.get(DiscoveryProgressRecord, f"{self.settings.mode}:{venue}")
            return dict(row.payload) if row else {}

    async def scan(self, adapter):
        if adapter.venue not in {"kalshi", "polymarket_us"}:
            raise ValueError("Broad discovery is supported only for Kalshi and Polymarket US")
        mode, venue = self.settings.mode, adapter.venue
        state = await self.progress(venue)
        token = state.get("continuation")
        if token is None:
            state["cycle_started_at"] = utcnow().isoformat()
        seen_pages = list(state.get("page_hashes", [])) if token is not None else []
        decisions, pages = [], 0
        watchlist = list(
            dict.fromkeys(adapter.tickers if venue == "kalshi" else adapter.market_ids)
        )
        page_size = self.settings.catalog_page_size
        for _ in range(self.settings.discovery_scan_pages):
            if watchlist:
                offset = int(token or 0)
                identifiers = watchlist[offset : offset + page_size]
                items = []
                for external_id in identifiers:
                    base = (
                        "https://external-api.kalshi.com/trade-api/v2/markets/"
                        if venue == "kalshi"
                        else "https://gateway.polymarket.us/v1/market/slug/"
                    )
                    response = await adapter.http.get(base + quote(external_id, safe=""))
                    item = response["market"]
                    if item.get("ticker" if venue == "kalshi" else "slug") != external_id:
                        raise ValueError("Watchlist identity mismatch")
                    items.append(item)
                next_token = offset + len(items) if offset + len(items) < len(watchlist) else None
            elif venue == "kalshi":
                response = await adapter.http.get(
                    "https://external-api.kalshi.com/trade-api/v2/markets",
                    params={"status": "open", "limit": page_size, "cursor": token or ""},
                )
                items, next_token = response["markets"], response.get("cursor") or None
            else:
                offset = int(token or 0)
                response = await adapter.http.get(
                    "https://gateway.polymarket.us/v1/markets",
                    params={
                        "active": "true",
                        "closed": "false",
                        "limit": page_size,
                        "offset": offset,
                    },
                )
                items = response["markets"]
                next_token = offset + len(items) if len(items) == page_size else None
            if not isinstance(items, list) or len(items) > page_size:
                raise ValueError("Invalid bounded catalog page")
            page_hash = digest(items)
            if page_hash in seen_pages or (next_token is not None and next_token == token):
                raise ValueError("Catalog pagination did not advance")
            seen_pages.append(page_hash)
            if len(seen_pages) > 10000:
                raise ValueError("Catalog pagination cycle exceeds supported bound")
            now = utcnow()
            async with self.repository.database.sessions.begin() as session:
                for item in items:
                    if not isinstance(item, dict):
                        raise ValueError("Invalid catalog item")
                    external_id = str(item.get("ticker" if venue == "kalshi" else "slug") or "")
                    # Malformed records remain inspectable without colliding with valid identities.
                    if not external_id:
                        external_id = "invalid:" + digest(item)
                    reason, market = None, None
                    try:
                        if venue == "kalshi":
                            reason, market = candidate(adapter, item, None)
                        else:
                            market = adapter.normalize_market(item)
                            if market.status != "open" or market.closes_at <= now:
                                reason = "closed_or_expired"
                    except (ValueError, KeyError, TypeError, ArithmeticError):
                        reason = "unsupported_or_invalid_instrument"
                    observation_id = digest(
                        {"mode": mode, "venue": venue, "external_id": external_id, "raw": item}
                    )
                    if await session.get(CatalogObservationRecord, observation_id) is None:
                        session.add(
                            CatalogObservationRecord(
                                id=observation_id,
                                mode=mode,
                                venue=venue,
                                external_id=external_id,
                                observed_at=now,
                                payload=item,
                            )
                        )
                        await session.flush()
                    await session.merge(
                        CatalogInventoryRecord(
                            key=f"{mode}:{venue}:{external_id}",
                            mode=mode,
                            venue=venue,
                            external_id=external_id,
                            observation_id=observation_id,
                            market_id=market.id if market else None,
                            supported=not bool(reason),
                            reason=reason or "supported_binary_candidate",
                            observed_at=now,
                        )
                    )
                    if market:
                        # Same page and progress commit atomically with the normalized projection.
                        await self.repository.save_market_in_session(session, market)
                    decisions.append(
                        DiscoveryDecision(
                            external_id=external_id,
                            family="watchlist" if watchlist else "catalog",
                            included=not bool(reason),
                            reason=reason or "supported_binary_candidate",
                        )
                    )
                state.update(
                    {
                        "continuation": next_token,
                        "page_hashes": seen_pages if next_token is not None else [],
                        "coverage_complete": next_token is None
                        and datetime.fromisoformat(state["cycle_started_at"])
                        > now - timedelta(seconds=self.settings.catalog_max_age_seconds),
                        "last_page_at": now.isoformat(),
                    }
                )
                await session.merge(
                    DiscoveryProgressRecord(
                        key=f"{mode}:{venue}",
                        mode=mode,
                        venue=venue,
                        payload=state,
                    )
                )
            pages += 1
            token = next_token
            if token is None:
                break
        return DiscoveryScan(
            markets=tuple(await self.markets(venue)),
            decisions=tuple(decisions),
            pages_scanned=pages,
            truncated=token is not None,
        )

    async def markets(self, venue):
        from arbbot.domain import Market

        cutoff = utcnow() - timedelta(seconds=self.settings.catalog_max_age_seconds)
        async with self.repository.database.sessions() as session:
            rows = (
                await session.scalars(
                    select(MarketRecord)
                    .join(
                        CatalogInventoryRecord,
                        (CatalogInventoryRecord.market_id == MarketRecord.id)
                        & (CatalogInventoryRecord.mode == MarketRecord.mode),
                    )
                    .where(
                        CatalogInventoryRecord.mode == self.settings.mode,
                        CatalogInventoryRecord.venue == venue,
                        CatalogInventoryRecord.supported.is_(True),
                        CatalogInventoryRecord.observed_at > cutoff,
                    )
                    .order_by(MarketRecord.id)
                )
            ).all()
        return [restore(Market, row.payload) for row in rows]
