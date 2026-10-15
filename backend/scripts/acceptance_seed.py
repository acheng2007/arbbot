"""Seed reviewed synthetic evidence through the normal revision-aware repositories."""

import getpass
from datetime import timedelta

import httpx
from acceptance_dataset import definition

from arbbot.discovery.service import CatalogService
from arbbot.domain import utcnow
from arbbot.exchanges.recorded import RecordedAdapter, RecordedExchange
from arbbot.exchanges.simulation import simulation_reviews
from arbbot.execution.models import (
    AccessProfile,
    Applicability,
    Citation,
    ConfigurationWrite,
    Permission,
)
from arbbot.execution.repository import ExecutionRepository
from arbbot.fees.refresh import FeeRefresh
from arbbot.reviews.models import Actor, DecisionWrite, DraftWrite
from arbbot.reviews.repository import ReviewRepository
from arbbot.sources.fetch import SourceFetcher
from arbbot.sources.models import SourceCapture
from arbbot.sources.repository import SourceRepository
from arbbot.storage.repository import Repository
from arbbot.venues import build_adapters

ACTOR = Actor(issuer="local-operator", subject=getpass.getuser())


async def seed(settings, database):
    repository, configuration = Repository(database), ExecutionRepository(database)
    reviews, sources = ReviewRepository(database), SourceRepository(database)
    recording = RecordedExchange(settings.recording_file)
    fetcher = SourceFetcher(transport=recording.transport, ttl=0)
    pairs, decisions = {}, {}
    async with httpx.AsyncClient(transport=recording.transport) as client:
        adapters = [RecordedAdapter(a) for a in build_adapters(client, settings, once=True)]
        catalog = CatalogService(settings, repository, adapters, source_fetcher=fetcher)
        for adapter in adapters:
            await catalog.refresh(adapter, enrich=False)
            all_markets = await catalog.inventory.markets(adapter.venue)
            for index in range(1, 5):
                identifier = f"{adapter.venue}:" + (
                    f"SYN-{index}" if adapter.venue == "kalshi" else f"synthetic-{index}"
                )
                market = next(m for m in all_markets if m.id == identifier)
                enriched = await adapter.enrich_sources(market, sources, fetcher)
                enriched = enriched.model_copy(
                    update={
                        "settlement_details": {
                            **enriched.settlement_details,
                            "catalog_input_hash": market.terms_hash,
                        }
                    }
                )
                await repository.save_market(enriched)
                host = (
                    "assets.kalshi.com" if adapter.venue == "kalshi" else "polymarketexchange.com"
                )
                citations = []
                for role, path in (("specification", "spec"), ("amendment_inventory", "notices")):
                    url = f"https://{host}/acceptance/{path}-{index}.txt"
                    content, media_type, received = await fetcher.read(url)
                    artifact = await sources.record(
                        SourceCapture(
                            mode="live",
                            market_id=market.id,
                            venue=market.venue,
                            url=url,
                            label=role,
                            content=content,
                            content_type=media_type,
                            retrieved_at=received,
                            details={"synthetic_acceptance": True},
                        )
                    )
                    citations.append(
                        Citation(
                            artifact_id=artifact.id,
                            content_hash=artifact.content_digest,
                            quotation=content.decode(),
                        )
                    )
                await configuration.save(
                    "live",
                    ConfigurationWrite(
                        value=Applicability(
                            market_id=market.id,
                            terms_hash=enriched.terms_hash,
                            product_id=f"synthetic-{index}",
                            status="verified",
                            specifications=(citations[0],),
                            amendment_inventory=citations[1],
                            rationale=(
                                "Explicitly synthetic product and shared "
                                "exceptional settlement evidence"
                            ),
                            expires_at=utcnow() + timedelta(hours=1),
                        ),
                        reason="Review isolated synthetic applicability",
                    ),
                    ACTOR,
                )
                market = await repository.market("live", market.id)
                draft = await reviews.save_draft(
                    "live",
                    market.id,
                    DraftWrite(
                        definition=definition(market, index),
                        source_artifact_ids=tuple(c.artifact_id for c in citations),
                        reason=(
                            "Interpret explicit synthetic settlement facts without assumed values"
                        ),
                    ),
                    ACTOR,
                )
                pairs.setdefault(index, {})[adapter.venue] = (market, draft)
        for index, pair in pairs.items():
            left, right = pair["kalshi"], pair["polymarket_us"]
            # The simulation review only supplies explicitly synthetic joint cases and scenarios.
            review = simulation_reviews(
                [
                    left[0].model_copy(update={"mode": "simulation"}),
                    right[0].model_copy(update={"mode": "simulation"}),
                ]
            )[0]
            review = review.model_copy(
                update={
                    "left_terms_hash": left[0].terms_hash,
                    "right_terms_hash": right[0].terms_hash,
                    "left_definition_hash": left[1].definition_hash,
                    "right_definition_hash": right[1].definition_hash,
                }
            )
            decisions[index] = await reviews.save_decision(
                "live",
                DecisionWrite(
                    left_draft_id=left[1].id,
                    right_draft_id=right[1].id,
                    action="verified",
                    review=review,
                    reason="Approve only explicit synthetic shared settlement scenarios",
                ),
                ACTOR,
            )
        access = await configuration.save(
            "live",
            ConfigurationWrite(
                value=AccessProfile(
                    jurisdiction="SYNTHETIC TEST ONLY",
                    status="verified",
                    supporting_evidence=(
                        "Isolated synthetic acceptance installation, no actual accounts or funds",
                    ),
                    permissions=tuple(
                        Permission(
                            venue=venue,
                            market_ids=tuple(pairs[i][venue][0].id for i in (1, 2, 4)),
                            short_allowed=True,
                            fee_account_class="direct" if venue == "kalshi" else "standard",
                        )
                        for venue in ("kalshi", "polymarket_us")
                    ),
                    expires_at=utcnow() + timedelta(hours=1),
                ),
                reason=(
                    "Synthetic access permissions; scenario three "
                    "intentionally remains inaccessible"
                ),
            ),
            ACTOR,
        )
        markets = [item[0] for pair in pairs.values() for item in pair.values()]
        # Exercise actual policy retrieval, source extraction and immutable policy persistence.
        await FeeRefresh(
            settings.model_copy(update={"discovery_limit": 50}), repository, adapters, fetcher
        ).refresh(markets)
    return {"pairs": pairs, "decisions": decisions, "access": access}
