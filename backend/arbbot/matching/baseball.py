"""Narrow rule-backed World Series candidate identities, never settlement approval."""

import re

from arbbot.matching.contracts import Fact

# Explicit aliases scoped to championship rules. Ambiguous city-only LA/NY names are excluded.
TEAMS = {
    "Atlanta": "Atlanta Braves",
    "San Diego": "San Diego Padres",
    "Los Angeles D": "Los Angeles Dodgers",
    "Chicago W": "Chicago White Sox",
    "Philadelphia": "Philadelphia Phillies",
    "Milwaukee": "Milwaukee Brewers",
    "New York Y": "New York Yankees",
    "Cleveland": "Cleveland Guardians",
    "Tampa Bay": "Tampa Bay Rays",
    "Detroit": "Detroit Tigers",
    "Toronto": "Toronto Blue Jays",
    "Boston": "Boston Red Sox",
    "Seattle": "Seattle Mariners",
    "Houston": "Houston Astros",
    "New York M": "New York Mets",
    "Chicago C": "Chicago Cubs",
    "Baltimore": "Baltimore Orioles",
    "Texas": "Texas Rangers",
    "San Francisco": "San Francisco Giants",
    "Arizona": "Arizona Diamondbacks",
    "Cincinnati": "Cincinnati Reds",
    "Pittsburgh": "Pittsburgh Pirates",
    "St. Louis": "St. Louis Cardinals",
    "Kansas City": "Kansas City Royals",
    "Minnesota": "Minnesota Twins",
    "Miami": "Miami Marlins",
    "Washington": "Washington Nationals",
    "Colorado": "Colorado Rockies",
    "Los Angeles A": "Los Angeles Angels",
    "Athletics": "Athletics",
}
KALSHI = re.compile(
    r"^If (?P<team>.+) wins the (?P<year>20\d{2}) Pro Baseball Championship, "
    r"then the market resolves to Yes\."
)
US = re.compile(
    r"^Will (?P<team>.+) win the (?P<year>20\d{2}) MLB World Series, scheduled for [^?]+\?"
)


def baseball_facts(market):
    parser = {"kalshi": KALSHI, "polymarket_us": US}.get(market.venue)
    match = parser.match(market.rules) if parser else None
    if not match:
        return {}
    team = TEAMS.get(match["team"]) if market.venue == "kalshi" else match["team"]
    if team not in TEAMS.values():
        return {}
    values = {
        "event_type": "sports_championship",
        "entity": team,
        "metric": "mlb_world_series_winner",
        "reference_period": match["year"],
        "outcome_orientation": "yes_if_true",
        "operator": "binary",
    }
    return {
        name: Fact(value=value, source="rules", quote=match.group())
        for name, value in values.items()
    }
