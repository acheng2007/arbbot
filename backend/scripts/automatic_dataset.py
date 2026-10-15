"""Explicit synthetic complete terms plus unchanged authentic exchange recordings.

Bindings in this dataset model exact instrument/document relationships only for
synthetic examples. They are not evidence that any real venue pair qualifies.
"""

import base64
import json

from acceptance_dataset import create_recording

from arbbot.matching.contracts import REQUIRED_FIELDS


def rules(index):
    values = dict.fromkeys(REQUIRED_FIELDS, "not_applicable")
    values.update(
        event_type="economic_release",
        entity="US",
        metric="cpi",
        reference_period=f"2098-{index:02}",
        measurement="month-over-month",
        source="US_BLS",
        value_version="initial",
        operator=">",
        threshold="3",
        units="percent",
        observation_window=f"2098-{index:02}",
        timezone="UTC",
        outcome_orientation="yes_if_true",
        payout="one_usd",
        cancellation="fixed_half",
        exceptions="independent",
        seasonal_adjustment="seasonally_adjusted",
        rounding_increment="0.1",
        rounding_mode="half_even",
        revision_policy="initial_release",
        observation_start=f"2098-{index:02}-01T00:00:00+00:00",
        observation_end=f"2098-{index + 1:02}-01T00:00:00+00:00",
        observation_start_inclusive="true",
        observation_end_inclusive="false",
    )
    return "\n".join(f"{k.replace('_', ' ').capitalize()}: {v}" for k, v in values.items()) + (
        "\ncancellation: YES pays 0.5, NO pays 0.5."
        "\nfallback: not applicable.\nambiguous_resolution: not applicable."
    )


def create_automatic_recording(directory):
    path = create_recording(directory)
    data = json.loads(path.read_text())
    data["qualification_bindings"] = {}
    # Keep a small declared catalog for timing assertions. Pagination and
    # backpressure are independently exercised against larger catalogs in tests.
    for venue in data["catalogs"]:
        data["catalogs"][venue] = [
            raw
            for raw in data["catalogs"][venue]
            if not raw.get("synthetic")
            or (
                raw.get("ticker") in ("SYN-1", "SYN-2")
                if venue == "kalshi"
                else raw.get("slug") in ("synthetic-1", "synthetic-2")
            )
        ]
        for raw in data["catalogs"][venue]:
            if not raw.get("synthetic"):
                continue
            identifier = raw["ticker"] if venue == "kalshi" else raw["slug"]
            index = int(identifier.rsplit("-", 1)[1])
            text = rules(index)
            if index == 2:
                # A price gap with incomplete clause coverage stays potential.
                text = text.replace("fallback: not applicable.", "Fallback remains unspecified.")
            if venue == "kalshi":
                raw["rules_primary"], raw["rules_secondary"] = text, ""
                url = f"https://external-api.kalshi.com/trade-api/v2/markets/{identifier}"
            else:
                raw["description"] = text
                url = f"https://gateway.polymarket.us/v1/market/slug/{identifier}"
            data["responses"][url] = {
                "content_type": "application/json",
                "content_base64": base64.b64encode(json.dumps({"market": raw}).encode()).decode(),
            }
            host = "assets.kalshi.com" if venue == "kalshi" else "polymarketexchange.com"
            spec = f"https://{host}/automatic/spec-{index}.txt"
            data["qualification_bindings"][f"{venue}:{identifier}"] = {"specifications": [spec]}
            data["responses"][spec] = {
                "content_type": "text/plain",
                "content_base64": base64.b64encode(text.encode()).decode(),
            }
            # Both examples have positive gross price gaps, regardless of qualification.
            for book_url in data["books"]:
                if (venue == "kalshi" and f"/markets/{identifier}/" in book_url) or (
                    venue != "kalshi" and f"/markets/{identifier}/" in book_url
                ):
                    first = identifier.replace("-2", "-1")
                    source = book_url.replace(identifier, first)
                    data["books"][book_url] = json.loads(json.dumps(data["books"][source]))
                    if venue != "kalshi":
                        for body in data["books"][book_url].values():
                            body["marketData"]["marketSlug"] = identifier
    path.write_text(json.dumps(data))
    return path
