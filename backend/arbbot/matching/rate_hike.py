"""Partial drafts for recorded Fed rate-hike wording; windows remain explicit."""

import re
from datetime import datetime

from arbbot.matching.contracts import Fact

KALSHI = re.compile(
    r"^If the Federal Reserve announces an increase in the target range or target level "
    r"for the federal funds rate after market Issuance and on or before "
    r"(?P<end>[A-Z][a-z]{2} \d{1,2}, (?P<year>20\d{2})), then the market resolves to Yes\.$"
)
POLYMARKET = re.compile(
    r'^This market will resolve to ["“]Yes["”] if the upper bound of the target federal funds rate '
    r"is increased at any point between (?P<start>[A-Z][a-z]+ \d{1,2}, (?P<year>20\d{2})) "
    r"and the completion of the Fed's (?P<month>[A-Z][a-z]+) (?P<end_year>20\d{2}) meeting, "
    r"currently scheduled for [A-Z][a-z]+ \d{1,2} to \d{1,2}, 20\d{2}, "
    r"inclusive of any rate hike announced as a result of the [A-Z][a-z]+ meeting\."
)


def rate_hike_facts(market):
    match = (KALSHI if market.venue == "kalshi" else POLYMARKET).match(
        market.rules.split("\n", 1)[0] if market.venue == "kalshi" else market.rules
    )
    if not match:
        return {}
    try:
        if market.venue == "kalshi":
            end = datetime.strptime(match["end"], "%b %d, %Y").date()
            window = f"after_market_issuance/through_{end.isoformat()}"
            measurement = "target_range_or_level"
        else:
            if match["year"] != match["end_year"]:
                return {}
            start = datetime.strptime(match["start"], "%B %d, %Y").date()
            meeting = datetime.strptime(f"{match['month']} {match['end_year']}", "%B %Y")
            if start > meeting.date().replace(day=28):
                return {}
            window = f"{start.isoformat()}/through_{meeting:%Y-%m}_fomc_decision"
            measurement = "upper_bound"
    except ValueError:
        return {}
    values = {
        "event_type": "monetary_policy",
        "entity": "US",
        "metric": "federal_funds_rate_increase",
        "reference_period": match["year"],
        "measurement": measurement,
        "observation_window": window,
        "outcome_orientation": "yes_if_true",
    }
    return {
        name: Fact(value=value, source="rules", quote=match.group())
        for name, value in values.items()
    }
