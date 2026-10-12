"""Fee failures withdraw rather than substituting costs; bounded cohorts rotate durably."""

from datetime import timedelta

import httpx

from arbbot.domain import utcnow
from arbbot.execution.models import AccessProfile, ConfigurationWrite, Permission
from arbbot.execution.repository import ExecutionRepository
from arbbot.fees.refresh import FeeRefresh
from arbbot.reviews.models import Actor


async def test_fee_refresh_isolates_failure_and_rotates_after_restart(database, fixture_market):
    settings, db, repository = database
    settings = settings.model_copy(update={"mode": "live", "discovery_limit": 1})
    originals = fixture_market[0]
    markets = []
    for venue, original in zip(("kalshi", "polymarket_us"), originals, strict=True):
        for i in range(3):
            market = original.model_copy(
                update={
                    "id": f"{venue}:FEE-{i}",
                    "external_id": f"FEE-{i}",
                    "venue": venue,
                    "mode": "live",
                }
            )
            markets.append(market)
            await repository.save_market(market)
    actor = Actor(issuer="local-operator", subject="synthetic-fee-reviewer")
    store = ExecutionRepository(db)
    await store.save(
        "live",
        ConfigurationWrite(
            value=AccessProfile(
                jurisdiction="SYNTHETIC",
                status="verified",
                permissions=tuple(
                    Permission(
                        venue=v,
                        market_ids=tuple(m.id for m in markets if m.venue == v),
                        short_allowed=True,
                        fee_account_class="direct" if v == "kalshi" else "standard",
                    )
                    for v in ("kalshi", "polymarket_us")
                ),
                supporting_evidence=("Synthetic test profile only",),
                expires_at=utcnow() + timedelta(hours=1),
            ),
            reason="Permit synthetic fee refresh testing",
        ),
        actor,
    )
    selected = []

    async def refresh_market(market, permission):
        selected.append(market.id)
        if market.venue == "kalshi":
            raise httpx.ReadTimeout("Do not expose provider exception text")

    for _ in range(3):
        refresh = FeeRefresh(settings, repository, [], None)
        refresh._refresh_market = refresh_market
        await refresh.refresh(markets)
    assert set(selected) == {m.id for m in markets}
    async with db.sessions() as session:
        blocked = await store.current(session, "live:fees:kalshi:FEE-0")
        assert blocked.value.kind == "fee_unavailable" and blocked.value.reason == "provider_error"
        assert "Do not expose" not in blocked.model_dump_json()


def test_general_fee_formula_uses_first_formula_not_intro_or_examples():
    from decimal import Decimal
    from pathlib import Path
    from pypdf import PdfReader
    from arbbot.fees.refresh import documented_general_rate

    body = "\n".join(
        page.extract_text()
        for page in PdfReader(Path(__file__).parent / "fixtures/acceptance/kalshi-fees.pdf").pages
    )
    assert documented_general_rate(body) == Decimal("0.07")
    assert documented_general_rate(body.replace("0.07", "0.08", 1)) == Decimal("0.08")
