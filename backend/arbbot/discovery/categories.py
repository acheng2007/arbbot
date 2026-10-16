"""Browsing taxonomy only. A category never establishes event equivalence."""

import re

CATEGORIES = ("politics", "economics", "sports", "other", "unknown")
ALIASES = {
    "politics": {"politics", "elections", "election", "government", "political"},
    "economics": {"economics", "economy", "financials", "finance", "business", "economic"},
    "sports": {"sports", "sport", "baseball", "basketball", "football", "soccer"},
}


def category_group(value):
    if not value or not value.strip():
        return "unknown"
    tokens = set(re.findall(r"[a-z]+", value.casefold()))
    return next((name for name, aliases in ALIASES.items() if aliases & tokens), "other")
