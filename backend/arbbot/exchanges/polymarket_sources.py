"""Preserve documented Gamma market and event descriptions as source evidence."""

from urllib.parse import quote

from arbbot.sources.fetch import EvidenceCollector

GAMMA = "https://gamma-api.polymarket.com"


async def enrich_polymarket(market, repository, fetcher):
    collector = EvidenceCollector(market, repository, fetcher)
    data = await collector.get(
        GAMMA + "/markets/" + quote(market.external_id, safe=""), json_document=True
    )
    if not data or str(data.get("id")) != market.external_id:
        collector.issues.append("missing_or_wrong_market")
        return collector.finish({})
    evidence = {k: data.get(k) for k in ("id", "description", "resolutionSource", "conditionId")}
    if data.get("description") != market.rules or data.get("conditionId") != market.raw.get(
        "conditionId"
    ):
        collector.issues.append("market_metadata_changed_during_capture")
    if not isinstance(data.get("description"), str) or not data["description"]:
        collector.issues.append("missing_description")
    # Event descriptions are supplemental context, not replacements for market rules.
    events = data.get("events")
    evidence["events"] = []
    if isinstance(events, list):
        for event in events[:8]:
            if isinstance(event, dict):
                evidence["events"].append(
                    {
                        k: event.get(k)
                        for k in (
                            "id",
                            "description",
                            "resolutionSource",
                        )
                    }
                )
            else:
                collector.issues.append("malformed_event")
        if len(events) > 8:
            collector.issues.append("event_limit_reached")
    elif events is not None:
        collector.issues.append("malformed_events")
    urls = [data.get("resolutionSource")]
    urls.extend(event.get("resolutionSource") for event in evidence["events"])
    for url in dict.fromkeys(value for value in urls if isinstance(value, str) and value):
        await collector.get(url)
    if not isinstance(data.get("resolutionSource"), str) or not data["resolutionSource"]:
        collector.issues.append("missing_resolution_source")
    # Gamma documents no comprehensive post-publication clarification feed.
    collector.issues.append("supplemental_clarifications_unverified")
    return collector.finish(evidence)
