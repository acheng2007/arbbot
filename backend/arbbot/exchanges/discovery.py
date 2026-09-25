"""Venue-specific discovery requests. Results are candidates, never equivalence."""

import re
from collections import deque
from math import ceil
from urllib.parse import quote

from arbbot.discovery.models import DiscoveryDecision, DiscoveryScan
from arbbot.domain import utcnow


async def scan_catalog(adapter, families, limit, max_pages):
    watchlist = adapter.tickers if adapter.venue == "kalshi" else adapter.market_ids
    if watchlist:
        # Existing explicit watchlists retain absolute precedence over family search.
        markets, decisions = [], []
        ids = list(dict.fromkeys(watchlist))
        for external_id in ids[:limit]:
            if adapter.venue == "kalshi":
                data = await adapter.http.get(
                    "https://external-api.kalshi.com/trade-api/v2/markets/"
                    + quote(external_id, safe="")
                )
                item = data["market"]
            else:
                item = await adapter.http.get(
                    "https://gamma-api.polymarket.com/markets/" + quote(external_id, safe="")
                )
            reason, market = candidate(adapter, item, None)
            if market is not None and market.external_id != external_id:
                reason = "wrong_market_identity"
            if not reason:
                markets.append(market)
            decisions.append(
                DiscoveryDecision(
                    external_id=external_id,
                    family="watchlist",
                    included=not bool(reason),
                    reason=reason or "explicit_watchlist",
                )
            )
        return DiscoveryScan(
            markets=tuple(markets),
            decisions=tuple(decisions),
            pages_scanned=len(ids[:limit]),
            truncated=len(ids) > limit,
        )

    searches = deque(
        (family, term, None)
        for family in families
        for term in (
            family.kalshi_series if adapter.venue == "kalshi" else family.polymarket_queries
        )
    )
    markets, decisions, seen, cursors = {}, [], set(), set()
    pages = 0
    truncated = False
    per_search_limit = max(1, ceil(limit / len(searches)))
    selected_counts = {}
    while searches and pages < max_pages and len(markets) < limit and len(decisions) < 2000:
        family, term, cursor = searches.popleft()
        if adapter.venue == "kalshi":
            data = await adapter.http.get(
                "https://external-api.kalshi.com/trade-api/v2/markets",
                params={
                    "series_ticker": term,
                    "status": "open",
                    "mve_filter": "exclude",
                    "limit": 100,
                    "cursor": cursor or "",
                },
            )
            items = data["markets"]
            next_cursor = data.get("cursor")
        else:
            data = await adapter.http.get(
                "https://gamma-api.polymarket.com/public-search",
                params={
                    "q": term,
                    "events_status": "active",
                    "limit_per_type": 20,
                    "page": cursor or 1,
                    "keep_closed_markets": 0,
                    "search_tags": "false",
                    "search_profiles": "false",
                },
            )
            items = [
                market
                for event in data.get("events") or []
                for market in event.get("markets") or []
            ]
            next_cursor = (
                (cursor or 1) + 1 if (data.get("pagination") or {}).get("hasMore") else None
            )
        pages += 1
        if not isinstance(items, list):
            raise ValueError("Invalid discovery response")
        # Bound processing even if the exchange ignores the requested page size.
        if len(items) > 1000:
            truncated = True
        for item in items[:1000]:
            if len(decisions) >= 2000:
                truncated = True
                break
            external_id = str(item.get("ticker" if adapter.venue == "kalshi" else "id", ""))
            if (family.name, external_id) in seen or f"{adapter.venue}:{external_id}" in markets:
                continue
            seen.add((family.name, external_id))
            reason, market = candidate(adapter, item, family)
            if not reason and (
                len(markets) >= limit or selected_counts.get(term, 0) >= per_search_limit
            ):
                reason = "catalog_limit_reached"
                truncated = True
            if not reason:
                markets[market.id] = market
                selected_counts[term] = selected_counts.get(term, 0) + 1
            decisions.append(
                DiscoveryDecision(
                    external_id=external_id,
                    family=family.name,
                    included=not bool(reason),
                    reason=reason or "event_family_candidate",
                )
            )
        if next_cursor and selected_counts.get(term, 0) >= per_search_limit:
            truncated = True
        elif next_cursor:
            cursor_key = (term, str(next_cursor))
            if cursor_key in cursors:
                truncated = True
            else:
                cursors.add(cursor_key)
                searches.append((family, term, next_cursor))
    return DiscoveryScan(
        markets=tuple(markets.values()),
        decisions=tuple(decisions),
        pages_scanned=pages,
        truncated=truncated or bool(searches),
    )


def candidate(adapter, item, family):
    reason = exclusion(adapter, item, family)
    if reason:
        return reason, None
    try:
        market = adapter.normalize_market(item)
        if market.status != "open" or market.closes_at <= utcnow():
            return "closed_or_expired", market
        return None, market
    except (ValueError, KeyError, TypeError):
        return "invalid_market_metadata", None


def exclusion(adapter, item, family):
    from decimal import Decimal, InvalidOperation

    if adapter.venue == "kalshi":
        if item.get("market_type") != "binary" or item.get("mve_collection_ticker"):
            return "unsupported_outcomes"
        try:
            if Decimal(str(item.get("notional_value_dollars", "1"))) != 1:
                return "unsupported_payout"
        except InvalidOperation:
            return "invalid_market_metadata"
    else:
        if item.get("negRisk"):
            return "unsupported_negative_risk"
        try:
            if not adapter.supported(item):
                return "unsupported_outcomes"
        except (ValueError, TypeError):
            return "invalid_market_metadata"
    # A publisher citation in unrelated rules is not an event-family signal.
    # Headline relevance only selects candidates; it never establishes equivalence.
    text = " ".join(str(item.get(k) or "") for k in ("title", "question"))
    if family is not None and not any(
        re.search(r"\b" + re.escape(word) + r"\b", text, re.IGNORECASE) for word in family.keywords
    ):
        return "unrelated_event_family"
    return None
