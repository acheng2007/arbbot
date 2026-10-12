"""Independent synthetic scenarios plus unchanged authentic exchange recordings."""

import base64
import hashlib
import json
from pathlib import Path

from arbbot.matching.contracts import (
    REQUIRED_FIELDS,
    ContractDefinition,
    Fact,
    SettlementCondition,
    SettlementPolicy,
)

ROOT = Path(__file__).resolve().parents[1] / "tests/fixtures"


def facts(index):
    values = dict.fromkeys(REQUIRED_FIELDS, "not_applicable")
    values.update(
        event_type="synthetic_threshold",
        entity=f"scenario_{index}",
        metric="synthetic_index",
        reference_period="2098-12",
        measurement="level",
        source="synthetic_fixture",
        value_version="initial",
        operator=">",
        threshold="100",
        units="points",
        observation_window="2098-12",
        timezone="UTC",
        outcome_orientation="yes_if_true",
        payout="one_usd",
        cancellation="fixed_half",
        exceptions="shared_cancellation",
        seasonal_adjustment="not_applicable",
        rounding_increment="1",
        rounding_mode="half_even",
        revision_policy="initial_release",
        observation_start="2098-12-01T00:00:00+00:00",
        observation_end="2099-01-01T00:00:00+00:00",
        observation_start_inclusive="true",
        observation_end_inclusive="false",
    )
    return values


def rules(index):
    return (
        "SYNTHETIC ACCEPTANCE FIXTURE. Not an exchange contract.\n"
        + "\n".join(f"{key}={value}" for key, value in facts(index).items())
        + (
            "\nSynthetic cancellation is a single shared event on both venues together; "
            "YES and NO each pay 0.5 USD. No fallback or ambiguous-resolution conditions apply."
        )
    )


def definition(market, index):
    return ContractDefinition(
        market_id=market.id,
        terms_hash=market.terms_hash,
        extractor="synthetic-acceptance-reviewed-v1",
        schema_version=2,
        facts={
            key: Fact(value=value, source="rules", quote=f"{key}={value}")
            for key, value in facts(index).items()
        },
        settlement_policies=(
            SettlementPolicy(
                kind="cancellation",
                status="modeled",
                evidence=Fact(
                    value="fixed_half", source="rules", quote="YES and NO each pay 0.5 USD."
                ),
                conditions=(
                    SettlementCondition(
                        id="cancelled",
                        trigger="Synthetic shared cancellation",
                        yes_payout="0.5",
                        no_payout="0.5",
                    ),
                ),
            ),
            *(
                SettlementPolicy(
                    kind=kind,
                    status="not_applicable",
                    evidence=Fact(
                        value="not_applicable",
                        source="rules",
                        quote="No fallback or ambiguous-resolution conditions apply.",
                    ),
                )
                for kind in ("fallback", "ambiguous_resolution")
            ),
        ),
    )


def kalshi(index):
    return {
        "synthetic": True,
        "ticker": f"SYN-{index}",
        "event_ticker": f"SYN-E-{index}",
        "title": f"SYNTHETIC: Scenario {index}",
        "category": "acceptance",
        "market_type": "binary",
        "status": "active",
        "close_time": "2099-01-01T00:00:00Z",
        "notional_value_dollars": "1",
        "rules_primary": rules(index),
        "rules_secondary": "",
        "mve_selected_legs": [],
        "price_ranges": [{"start": "0", "end": "1", "step": "0.01"}],
    }


def us(index, suffix=""):
    slug = f"synthetic-{index}{suffix}"
    return {
        "synthetic": True,
        "slug": slug,
        "question": "SYNTHETIC",
        "title": f"Scenario {index}",
        "description": rules(index),
        "endDate": "2099-01-01T00:00:00Z",
        "category": "acceptance",
        "marketType": "binary",
        "active": True,
        "closed": False,
        "status": "MARKET_STATUS_OPEN",
        "minimumTradeQty": "1",
        "orderPriceMinTickSize": "0.01",
        "marketSides": [
            {
                "description": side,
                "marketSideType": "MARKET_SIDE_TYPE_INSTRUMENT",
                "identifier": slug,
                "long": side == "Yes",
                "quote": {"currency": "USD"},
            }
            for side in ("Yes", "No")
        ],
    }


def book(venue, identifier, *, adverse=False, unprofitable=False):
    if venue == "kalshi":
        bids = "0.01" if adverse else "0.40" if unprofitable else "0.05"
        no_bids = "0.01" if adverse else "0.40" if unprofitable else "0.90"
        return {
            "synthetic": True,
            "orderbook_fp": {"yes_dollars": [[bids, "10.00"]], "no_dollars": [[no_bids, "10.00"]]},
        }
    bid, ask = (
        ("0.01", "0.99") if adverse else ("0.40", "0.60") if unprofitable else ("0.90", "0.95")
    )
    return {
        "synthetic": True,
        "marketData": {
            "marketSlug": identifier,
            "state": "MARKET_STATE_OPEN",
            "transactTime": "2099-01-01T00:00:00+00:00",
            "offers": [{"px": {"currency": "USD", "value": ask}, "qty": "10"}],
            "bids": [{"px": {"currency": "USD", "value": bid}, "qty": "10"}],
        },
    }


def create_recording(directory):
    directory.mkdir(parents=True, exist_ok=True)
    control, journal = directory / "control.json", directory / "requests.jsonl"
    control.write_text(
        json.dumps({"epoch": 0, "phase": "baseline", "quote_lag_seconds": {"synthetic-4": 60}})
    )
    journal.write_text("")
    data = {
        "format": "arbbot-recorded-exchange-v1",
        "control_file": str(control),
        "journal_file": str(journal),
        "catalogs": {"kalshi": [], "polymarket_us": []},
        "books": {},
        "responses": {},
    }

    def response(url, body, content_type="application/json"):
        content = (
            json.dumps(body).encode()
            if isinstance(body, dict)
            else body
            if isinstance(body, bytes)
            else body.encode()
        )
        data["responses"][url] = {
            "content_type": content_type,
            "content_base64": base64.b64encode(content).decode(),
        }

    for index in range(1, 5):
        raw_k, raw_u = kalshi(index), us(index)
        for venue, raw, identifier, url in (
            (
                "kalshi",
                raw_k,
                raw_k["ticker"],
                f"https://external-api.kalshi.com/trade-api/v2/markets/{raw_k['ticker']}/orderbook",
            ),
            (
                "polymarket_us",
                raw_u,
                raw_u["slug"],
                f"https://gateway.polymarket.us/v1/markets/{raw_u['slug']}/book",
            ),
        ):
            data["catalogs"][venue].append(raw)
            data["books"][url] = {
                phase: book(venue, identifier, adverse=phase == "adverse", unprofitable=index == 2)
                for phase in ("baseline", "adverse")
            }
        base = "https://external-api.kalshi.com/trade-api/v2"
        response(base + f"/markets/SYN-{index}", {"market": raw_k})
        response(
            base + f"/events/SYN-E-{index}",
            {"event": {"event_ticker": f"SYN-E-{index}", "series_ticker": f"SYN-S-{index}"}},
        )
        response(
            base + f"/series/SYN-S-{index}",
            {
                "series": {
                    "ticker": f"SYN-S-{index}",
                    "fee_type": "quadratic",
                    "fee_multiplier": "1",
                    "settlement_sources": [
                        {
                            "url": f"https://assets.kalshi.com/acceptance/spec-{index}.txt",
                            "name": "Synthetic",
                        }
                    ],
                    "contract_url": f"https://assets.kalshi.com/acceptance/spec-{index}.txt",
                    "contract_terms_url": f"https://assets.kalshi.com/acceptance/spec-{index}.txt",
                }
            },
        )
        response(
            f"https://gateway.polymarket.us/v1/market/slug/synthetic-{index}", {"market": raw_u}
        )
        for host in ("assets.kalshi.com", "polymarketexchange.com"):
            response(f"https://{host}/acceptance/spec-{index}.txt", rules(index), "text/plain")
            response(
                f"https://{host}/acceptance/notices-{index}.txt",
                f"SYNTHETIC scenario {index}: reviewed amendment inventory is empty.",
                "text/plain",
            )
    for index in range(205):
        raw = us(3, suffix=f"-counterpart-{index:03d}")
        data["catalogs"]["polymarket_us"].append(raw)
        response(f"https://gateway.polymarket.us/v1/market/slug/{raw['slug']}", {"market": raw})
        data["books"][f"https://gateway.polymarket.us/v1/markets/{raw['slug']}/book"] = {
            p: book("polymarket_us", raw["slug"], adverse=p == "adverse")
            for p in ("baseline", "adverse")
        }
    for index in range(6):
        raw = kalshi(100 + index)
        raw.update(title=f"SYNTHETIC unrelated instrument {index}", category="unrelated")
        data["catalogs"]["kalshi"].append(raw)
        data["books"][
            f"https://external-api.kalshi.com/trade-api/v2/markets/{raw['ticker']}/orderbook"
        ] = {
            p: book("kalshi", raw["ticker"], adverse=p == "adverse")
            for p in ("baseline", "adverse")
        }
    response(
        "https://external-api.kalshi.com/trade-api/v2/events/fee_changes",
        {"event_fee_changes": [], "cursor": ""},
    )
    response(
        "https://external-api.kalshi.com/trade-api/v2/series/fee_changes",
        {"series_fee_change_arr": []},
    )
    response(
        "https://polymarketexchange.com/files/legal/latest/Polymarket%20US%20Rulebook",
        "SYNTHETIC global fixture rulebook; no real venue settlement claims.",
        "text/plain",
    )
    for path in ("products", "notices"):
        response(f"https://polymarketexchange.com/files/{path}", {"files": []})
    for entry in json.loads((ROOT / "acceptance/manifest.json").read_text()):
        content = (ROOT / "acceptance" / entry["file"]).read_bytes()
        assert hashlib.sha256(content).hexdigest() == entry["sha256"]
        response(entry["url"], content, entry["content_type"])
    # Authentic settlement recordings remain byte-for-byte intact and unapproved.
    for venue, filename, bookname, detail_url, book_url in (
        (
            "kalshi",
            "kalshi-dodgers.json",
            "kalshi-dodgers-book.json",
            "https://external-api.kalshi.com/trade-api/v2/markets/KXMLB-26-LAD",
            "https://external-api.kalshi.com/trade-api/v2/markets/KXMLB-26-LAD/orderbook",
        ),
        (
            "polymarket_us",
            "polymarket-us-dodgers.json",
            "polymarket-us-dodgers-book.json",
            "https://gateway.polymarket.us/v1/market/slug/tec-mlb-champ-2026-09-27-lad",
            "https://gateway.polymarket.us/v1/markets/tec-mlb-champ-2026-09-27-lad/book",
        ),
    ):
        content = (ROOT / "us_venues" / filename).read_bytes()
        body = json.loads(content)
        data["catalogs"][venue].append(body["market"])
        response(detail_url, content)
        recorded_book = json.loads((ROOT / "us_venues" / bookname).read_text())
        data["books"][book_url] = {"baseline": recorded_book, "adverse": recorded_book}
    path = directory / "recording.json"
    path.write_text(json.dumps(data))
    return path
