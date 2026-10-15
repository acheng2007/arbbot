"""Explicit offline exchange replay. Every request must match an on-disk recording."""

import base64
import json
from datetime import timedelta
from pathlib import Path

import httpx

from arbbot.domain import utcnow


class RecordedExchange:
    def __init__(self, path: Path):
        self.recording = json.loads(path.read_text())
        if self.recording.get("format") != "arbbot-recorded-exchange-v1":
            raise ValueError("Unsupported exchange recording")
        self.control = Path(self.recording["control_file"])
        self.journal = Path(self.recording["journal_file"])
        self.epoch, self.counts = None, {}
        self.transport = httpx.MockTransport(self.handle)
        self.qualification_bindings = self.recording.get("qualification_bindings", {})

    def handle(self, request):
        if request.method != "GET":
            return httpx.Response(405, json={"error": "recorded exchange replay is read-only"})
        state = json.loads(self.control.read_text())
        epoch = state.get("epoch", 0)
        if epoch != self.epoch:
            self.epoch, self.counts = epoch, {}
        url = str(request.url.copy_with(query=None))
        venue = "kalshi" if request.url.host == "external-api.kalshi.com" else "polymarket_us"
        kind = (
            "book"
            if url in self.recording["books"]
            else "catalog"
            if (request.url.path in ("/trade-api/v2/markets", "/v1/markets"))
            else "source"
        )
        with self.journal.open("a") as journal:
            journal.write(
                json.dumps(
                    {
                        "at": utcnow().isoformat(),
                        "venue": venue,
                        "kind": kind,
                        "url": url,
                        "epoch": epoch,
                    }
                )
                + "\n"
            )
        if venue in state.get("outage", []) and kind in ("book", "catalog"):
            return httpx.Response(503, json={"error": "recorded venue outage"})
        if kind == "book":
            if state.get("freeze_books"):
                raise httpx.ReadTimeout("Recorded quote polling paused")
            self.counts[url] = self.counts.get(url, 0) + 1
            phase = (
                "adverse"
                if state.get("phase") == "adverse"
                or (state.get("phase") == "publication_move" and self.counts[url] > 1)
                else "baseline"
            )
            body = json.loads(json.dumps(self.recording["books"][url][phase]))
            if "marketData" in body and body.get("synthetic"):
                instant = utcnow() - timedelta(
                    seconds=state.get("quote_lag_seconds", {}).get(
                        body["marketData"]["marketSlug"], 0
                    )
                )
                body["marketData"]["transactTime"] = instant.isoformat()
                if state.get("invalid_book") == body["marketData"]["marketSlug"]:
                    body["marketData"]["state"] = "MARKET_STATE_HALTED"
            return httpx.Response(200, json=body)
        if kind == "catalog":
            items = self.recording["catalogs"][venue]
            offset = int(request.url.params.get("cursor") or request.url.params.get("offset") or 0)
            limit = int(request.url.params.get("limit") or 100)
            body = {"markets": items[offset : offset + limit]}
            if venue == "kalshi":
                body["cursor"] = str(offset + limit) if offset + limit < len(items) else ""
            return httpx.Response(200, json=body)
        if state.get("fee_failure") and (
            "fee_changes" in url
            or url
            in (
                "https://docs.polymarket.us/fees",
                "https://docs.kalshi.com/getting_started/fee_rounding",
            )
        ):
            return httpx.Response(503, json={"error": "recorded fee-provider outage"})
        response = self.recording["responses"].get(url)
        if response is None:
            # No fallback transport: missing recordings cannot access live exchanges.
            return httpx.Response(404, json={"error": "request absent from recording"})
        content = base64.b64decode(response["content_base64"])
        if state.get("source_changed") == url:
            content += b"\nSYNTHETIC AMENDMENT: settlement evidence changed.\n"
        return httpx.Response(
            200, content=content, headers={"content-type": response["content_type"]}
        )


class RecordedAdapter:
    """Production adapter delegation with explicit provenance on normalized markets."""

    def __init__(self, adapter, qualification_bindings=None):
        self.adapter = adapter
        self.qualification_bindings = qualification_bindings or {}

    def __getattr__(self, name):
        return getattr(self.adapter, name)

    def normalize_market(self, raw):
        market = self.adapter.normalize_market(raw)
        return market.model_copy(
            update={
                "feed_origin": "synthetic_recording"
                if raw.get("synthetic")
                else "recorded_exchange"
            }
        )

    async def discover(self, limit):
        return [self.normalize_market(m.raw) for m in await self.adapter.discover(limit)]

    async def enrich_sources(self, market, repository, fetcher):
        binding = self.qualification_bindings.get(market.id)
        if not binding:
            return await self.adapter.enrich_sources(market, repository, fetcher)
        if market.feed_origin != "synthetic_recording":
            raise ValueError("Recorded applicability bindings are only for synthetic contracts")
        from arbbot.sources.fetch import EvidenceCollector

        collector = EvidenceCollector(market, repository, fetcher)
        for url in binding["specifications"]:
            await collector.get(url, label="contract_terms")
        return collector.finish(
            {
                "recorded_synthetic_instrument": market.external_id,
                "applicability_transport": (
                    "explicit synthetic recording binding; not a live finding"
                ),
            }
        )

    async def fetch_book(self, market):
        book = await self.adapter.fetch_book(market)
        return book.model_copy(update={"feed_origin": market.feed_origin})
