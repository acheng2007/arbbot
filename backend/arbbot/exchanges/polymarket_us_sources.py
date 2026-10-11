"""Public gateway identity and official US rulebook/index evidence.

Document indexes are discovery evidence, not proof of product applicability.
The official end-user legal documentation links the US rulebook host.
No International or institutional/preproduction instrument is substituted.
"""

from urllib.parse import quote

from arbbot.sources.fetch import EvidenceCollector

BASE = "https://gateway.polymarket.us"
OFFICIAL = "https://polymarketexchange.com"


async def enrich_polymarket_us(market, repository, fetcher):
    from arbbot.exchanges.polymarket_us import PolymarketUSAdapter

    collector = EvidenceCollector(market, repository, fetcher)
    data = await collector.get(
        BASE + "/v1/market/slug/" + quote(market.external_id, safe=""),
        label="polymarket_us_market",
        json_document=True,
    )
    try:
        current = PolymarketUSAdapter.normalize_market(data["market"])
        if current.id != market.id or current.terms_hash != market.terms_hash:
            collector.issues.append("market_terms_changed_during_capture")
    except (TypeError, KeyError, ValueError, ArithmeticError):
        collector.issues.append("missing_or_wrong_gateway_instrument")
    evidence = {"description": market.rules, "gateway_instrument": market.external_id}
    await collector.get(
        OFFICIAL + "/files/legal/latest/Polymarket%20US%20Rulebook",
        label="polymarket_us_rulebook",
    )
    for path, label in (
        ("products", "polymarket_us_products"),
        ("notices", "polymarket_us_notices"),
    ):
        index = await collector.get(OFFICIAL + "/files/" + path, label=label, json_document=True)
        if not index or not isinstance(index.get("files"), list):
            collector.issues.append("missing_" + path + "_index")
        else:
            evidence[path + "_index"] = index
    # A filename or matching title is insufficient to establish instrument identity.
    # A reviewer must establish applicable specifications and amendments explicitly.
    collector.issues.extend(
        ("product_specification_applicability_unverified", "clarification_applicability_unverified")
    )
    return collector.finish(evidence)
