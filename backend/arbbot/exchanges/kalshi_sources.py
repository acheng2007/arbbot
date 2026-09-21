"""Kalshi event/series evidence, without inference from ticker spelling."""

from urllib.parse import quote

from arbbot.sources.fetch import EvidenceCollector

BASE = "https://external-api.kalshi.com/trade-api/v2"


async def enrich_kalshi(market, repository, fetcher):
    collector = EvidenceCollector(market, repository, fetcher)
    evidence = {}
    event_ticker = market.settlement_details.get("event_ticker")
    if not isinstance(event_ticker, str) or not event_ticker:
        collector.issues.append("missing_event_reference")
        return collector.finish(evidence)
    data = await collector.get(BASE + "/events/" + quote(event_ticker, safe=""), json_document=True)
    event = data.get("event") if data else None
    if not isinstance(event, dict) or event.get("event_ticker") != event_ticker:
        collector.issues.append("missing_or_wrong_event")
        return collector.finish(evidence)
    evidence["event"] = {
        k: event.get(k)
        for k in (
            "event_ticker",
            "series_ticker",
            "mutually_exclusive",
            "collateral_return_type",
        )
    }
    series_ticker = event.get("series_ticker")
    if not isinstance(series_ticker, str) or not series_ticker:
        collector.issues.append("missing_series_reference")
        return collector.finish(evidence)
    data = await collector.get(
        BASE + "/series/" + quote(series_ticker, safe=""), json_document=True
    )
    series = data.get("series") if data else None
    if not isinstance(series, dict) or series.get("ticker") != series_ticker:
        collector.issues.append("missing_or_wrong_series")
        return collector.finish(evidence)
    evidence["series"] = {
        k: series.get(k)
        for k in (
            "ticker",
            "settlement_sources",
            "contract_url",
            "contract_terms_url",
            "additional_prohibitions",
        )
    }
    sources = series.get("settlement_sources")
    urls = []
    if not isinstance(sources, list) or not sources:
        collector.issues.append("missing_settlement_sources")
    else:
        for source in sources[:8]:
            if isinstance(source, dict) and isinstance(source.get("url"), str) and source["url"]:
                urls.append(source["url"])
            else:
                collector.issues.append("missing_source_url")
        if len(sources) > 8:
            collector.issues.append("source_limit_reached")
    for key in ("contract_url", "contract_terms_url"):
        value = series.get(key)
        if isinstance(value, str) and value:
            urls.append(value)
        else:
            collector.issues.append("missing_" + key)
    for url in dict.fromkeys(urls):
        await collector.get(url)
    return collector.finish(evidence)
