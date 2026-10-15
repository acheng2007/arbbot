"""Evaluate authentic, source-backed pair labels without fabricating model results."""

import argparse
import json
from pathlib import Path

from arbbot.exchanges.kalshi import KalshiAdapter
from arbbot.exchanges.polymarket_us import PolymarketUSAdapter
from arbbot.matching.extraction import extract_contract
from arbbot.matching.service import match_markets

ROOT = Path(__file__).resolve().parents[3]


def load_markets(row):
    return [
        KalshiAdapter.normalize_market(row["left"]["payload"]),
        PolymarketUSAdapter.normalize_market(row["right"]["payload"]),
    ]


def report(rows, responses=None):
    positive = sum(r["event_label"] == "same_event" for r in rows)
    baseline, supported, incorrect, abstained, covered = 0, 0, 0, 0, 0
    for row in rows:
        markets = load_markets(row)
        baseline += row["event_label"] == "same_event" and bool(
            match_markets(markets, [], [extract_contract(m).definition for m in markets])
        )
        result = (responses or {}).get(row["id"])
        if not result:
            continue
        covered += 1
        answer = result["answers"]["event"]
        suggestion = (
            answer["choice"] == "same_event"
            and answer["confidence"] >= 0.80
            and answer["probabilities"].get("same_event", 0) >= 0.80
        )
        supported += row["event_label"] == "same_event" and (
            suggestion
            or bool(match_markets(markets, [], [extract_contract(m).definition for m in markets]))
        )
        incorrect += suggestion and row["event_label"] != "same_event"
        abstained += answer["choice"] == "insufficient_evidence"
    return {
        "authentic_pairs": len(rows),
        "positive_labels": positive,
        "baseline_recall": baseline / positive if positive else None,
        "jev_assisted_recall": supported / positive if covered == len(rows) and positive else None,
        "incorrect_suggestions": incorrect if covered else None,
        "abstentions": abstained if covered else None,
        "model_response_coverage": covered / len(rows),
        "insufficient_clause_evidence_cases": sum(
            "insufficient_evidence" in r["clause_labels"].values() for r in rows
        ),
        "limitations": [
            "Authentic October 1 catalog snapshot, not a representative statistical sample.",
            "Complete metadata has no uncertain event-identity gold cases.",
            "Insufficient-evidence labels cover missing applicable settlement documents.",
            "No synthetic or scripted model answers enter accuracy metrics.",
            "Absent authentic model responses leave assisted metrics unmeasured.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pairs", type=Path, default=ROOT / "backend/tests/fixtures/jev/benchmark.json"
    )
    parser.add_argument("--responses", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = json.loads(args.pairs.read_text())["pairs"]
    responses = json.loads(args.responses.read_text()) if args.responses else None
    args.output.write_text(json.dumps(report(rows, responses), indent=2) + "\n")


if __name__ == "__main__":
    main()
