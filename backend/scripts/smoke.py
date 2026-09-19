"""Exercise the running simulation API, worker, PostgreSQL, audit trail, and SSE."""

import argparse
import json
from decimal import Decimal

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()
    with httpx.Client(base_url=args.base_url, timeout=15) as client:

        def get(path):
            response = client.get(path)
            response.raise_for_status()
            return response.json()

        assert get("/health/ready")["status"] == "ready"
        status = get("/api/v1/status")
        assert status["mode"] == "simulation", "Smoke test expects explicitly simulated data"
        assert status["ingestion_healthy"], status
        assert len(get("/api/v1/markets")) == 2
        opportunities = get("/api/v1/opportunities")
        assert len(opportunities) == 1
        opportunity = opportunities[0]
        assert opportunity["classification"] == "simulation"
        assert isinstance(opportunity["net_profit"], str)
        assert Decimal(opportunity["net_profit"]) == Decimal("1.61")
        for leg in opportunity["legs"]:
            snapshot = get("/api/v1/snapshots/" + leg["book_id"])
            assert snapshot["market_id"] == leg["market_id"]
        review = opportunity["review"]
        for side in ("left", "right"):
            market_id, terms_hash = review[side + "_id"], review[side + "_terms_hash"]
            assert (
                get(f"/api/v1/markets/{market_id}/versions/{terms_hash}")["terms_hash"]
                == terms_hash
            )
        with client.stream("GET", "/api/v1/stream") as stream:
            stream.raise_for_status()
            assert stream.headers["content-type"].startswith("text/event-stream")
            for line in stream.iter_lines():
                if line.startswith("data: "):
                    event = json.loads(line[6:])
                    assert event["mode"] == "simulation"
                    assert len(event["opportunities"]) == 1
                    break
            else:
                raise AssertionError("SSE stream ended without a snapshot")
        assert get("/openapi.json")["info"]["title"] == "Arbbot API"
    print("PASS: PostgreSQL -> worker -> REST API -> audit records -> SSE")


if __name__ == "__main__":
    main()
