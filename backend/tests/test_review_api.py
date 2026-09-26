import asyncio

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from arbbot.api.app import create_app
from arbbot.domain import digest, utcnow
from arbbot.reviews.models import DraftWrite
from arbbot.sources.models import SourceCapture
from arbbot.sources.repository import SourceRepository
from tests.test_auth import AUDIENCE, ISSUER, access_token, public_key
from tests.test_contracts import definition


@pytest.fixture(scope="module")
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(params=["simulation", "live"])
async def review_api(database, fixture_market, signing_key, request):
    settings, db, repository = database
    for index, market in enumerate(fixture_market[0]):
        market = market.model_copy(
            update={"mode": request.param, "settlement_details": {"source_status": "captured"}}
        )
        fixture_market[0][index] = market
        await repository.save_market(market)
        await SourceRepository(db).record(
            SourceCapture(
                venue=market.venue,
                mode=market.mode,
                market_id=market.id,
                url=f"https://example.test/{market.venue}/rules",
                label="contract_terms",
                content=market.rules.encode(),
                content_type="text/plain",
                retrieved_at=utcnow(),
            )
        )
    settings = settings.model_copy(
        update={
            "mode": request.param,
            "auth_issuer": ISSUER,
            "auth_audience": AUDIENCE,
            "auth_jwks_url": ISSUER + "jwks",
        }
    )
    app = create_app(settings, db)
    app.state.authenticator.client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"keys": [public_key(signing_key)]})
        )
    )
    headers = {
        "Authorization": "Bearer " + access_token(signing_key),
        "Origin": "http://localhost:3000",
    }
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield app, client, headers
    finally:
        await app.state.authenticator.close()


def draft_body(market, **updates):
    return {
        **DraftWrite(
            definition=definition(market), reason="Review the recorded market rules"
        ).model_dump(mode="json"),
        **updates,
    }


async def create_drafts(client, headers, markets):
    drafts = []
    for market in markets:
        sources = (await client.get(f"/api/v1/markets/{market.id}/sources")).json()
        result = await client.post(
            f"/api/v1/markets/{market.id}/drafts",
            headers=headers,
            json=draft_body(market, source_artifact_ids=[s["id"] for s in sources]),
        )
        assert result.status_code == 201, result.text
        drafts.append(result.json())
    return drafts


async def test_authenticated_draft_decision_history_and_revocation(review_api, fixture_market):
    _, client, headers = review_api
    markets, _, review, _ = fixture_market
    drafts = await create_drafts(client, headers, markets)
    for draft in drafts:
        assert draft["actor"]["audit_id"] == digest([ISSUER, "reviewer-123"])
        response = await client.get(f"/api/v1/drafts/{draft['id']}", headers=headers)
        assert response.json() == draft
    review_body = review.model_dump(mode="json")
    review_body.update(
        left_terms_hash=drafts[0]["market"]["terms_hash"],
        right_terms_hash=drafts[1]["market"]["terms_hash"],
        left_definition_hash=drafts[0]["definition_hash"],
        right_definition_hash=drafts[1]["definition_hash"],
        reviewer="spoofed",
    )
    body = {
        "left_draft_id": drafts[0]["id"],
        "right_draft_id": drafts[1]["id"],
        "action": "verified",
        "reason": "Approve reviewed synthetic conditions",
        "review": review_body,
    }
    approved = await client.post("/api/v1/reviews", headers=headers, json=body)
    assert approved.status_code == 201, approved.text
    assert approved.json()["review"]["reviewer"] == digest([ISSUER, "reviewer-123"])
    params = {"left_id": markets[1].id, "right_id": markets[0].id}
    current = await client.get("/api/v1/reviews/current", params=params, headers=headers)
    assert current.json()["eligible"]
    conflict = await client.post("/api/v1/reviews", headers=headers, json=body)
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["current_revision_id"] == approved.json()["id"]
    revoke = {
        **body,
        "action": "revoked",
        "review": None,
        "expected_revision_id": approved.json()["id"],
        "reason": "Revoke pending new evidence review",
    }
    revoked = await client.post("/api/v1/reviews", headers=headers, json=revoke)
    assert revoked.status_code == 201
    assert not (await client.get("/api/v1/reviews/current", params=params, headers=headers)).json()[
        "eligible"
    ]
    history = await client.get("/api/v1/reviews/history", params=params, headers=headers)
    assert [r["action"] for r in history.json()] == ["revoked", "verified"]


async def test_concurrent_http_draft_edits_have_one_winner(review_api, fixture_market):
    _, client, headers = review_api
    market = fixture_market[0][0]
    path = f"/api/v1/markets/{market.id}/drafts"
    first = (await client.post(path, headers=headers, json=draft_body(market))).json()
    results = await asyncio.gather(
        *(
            client.post(
                path, headers=headers, json=draft_body(market, expected_revision_id=first["id"])
            )
            for _ in range(2)
        )
    )
    assert sorted(r.status_code for r in results) == [201, 409]
    history = await client.get(path, params={"limit": 1, "offset": 1}, headers=headers)
    assert history.json() == [first]
    current = await client.get(f"/api/v1/markets/{market.id}/draft", headers=headers)
    assert current.json()["revision"] == 2


async def test_api_requires_identity_roles_and_allowed_origin(
    review_api, fixture_market, signing_key
):
    _, client, headers = review_api
    market = fixture_market[0][0]
    path = f"/api/v1/markets/{market.id}/drafts"
    assert (await client.get(path)).status_code == 401
    assert (await client.post(path, json=draft_body(market))).status_code == 401
    viewer = {"Authorization": "Bearer " + access_token(signing_key, scope="arbbot:read")}
    assert (await client.get(path, headers=viewer)).status_code == 200
    assert (await client.post(path, headers=viewer, json=draft_body(market))).status_code == 403
    assert (
        await client.post(
            path,
            headers={**headers, "Origin": "https://untrusted.example"},
            json=draft_body(market),
        )
    ).status_code == 403
    assert (
        await client.post(
            path, headers=headers, json=draft_body(market, actor={"subject": "spoofed"})
        )
    ).status_code == 422
    assert (await client.get(path, headers=headers, params={"limit": 101})).status_code == 422
    assert (await client.get(path, headers=headers)).json() == []


async def test_missing_market_and_invalid_evidence_are_explicit(review_api, fixture_market):
    _, client, headers = review_api
    market = fixture_market[0][0]
    assert (await client.get("/api/v1/markets/absent/draft", headers=headers)).status_code == 404
    assert (await client.get("/api/v1/drafts/absent", headers=headers)).status_code == 404
    body = draft_body(market)
    body["definition"]["facts"]["source"]["quote"] = "This quote is absent from the source rules"
    response = await client.post(f"/api/v1/markets/{market.id}/drafts", headers=headers, json=body)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_review_evidence"


async def test_review_revision_cannot_be_read_from_another_mode(
    review_api, fixture_market, database
):
    app, client, headers = review_api
    drafts = await create_drafts(client, headers, fixture_market[0])
    settings, db, _ = database
    other_mode = "simulation" if fixture_market[0][0].mode == "live" else "live"
    other_app = create_app(settings.model_copy(update={"mode": other_mode}), db)
    await other_app.state.authenticator.close()
    other_app.state.authenticator = app.state.authenticator
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=other_app), base_url="http://other"
    ) as other:
        assert (
            await other.get(f"/api/v1/drafts/{drafts[0]['id']}", headers=headers)
        ).status_code == 404
        assert (
            await other.get(f"/api/v1/markets/{fixture_market[0][0].id}/drafts", headers=headers)
        ).status_code == 404


async def test_changed_terms_return_conflict_without_saving_revision(
    review_api, fixture_market, database
):
    _, client, headers = review_api
    market = fixture_market[0][0]
    _, _, repository = database
    await repository.save_market(
        market.model_copy(update={"rules": market.rules + " Changed rule."})
    )
    response = await client.post(
        f"/api/v1/markets/{market.id}/drafts", headers=headers, json=draft_body(market)
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "revision_conflict"
    assert (await client.get(f"/api/v1/markets/{market.id}/drafts", headers=headers)).json() == []
