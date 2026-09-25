import re
from difflib import SequenceMatcher
from itertools import combinations

from arbbot.domain import Market, Match, Review, digest, utcnow
from arbbot.matching.contracts import ContractDefinition, compare_contracts
from arbbot.matching.settlement import settlement_issues


def match_markets(
    markets: list[Market],
    reviews: list[Review],
    definitions: list[ContractDefinition] | None = None,
) -> list[Match]:
    contracts = {d.market_id: d for d in definitions or []}
    if len(contracts) != len(definitions or []):
        raise ValueError("Duplicate contract definitions for a market")
    indexed = {frozenset((r.left_id, r.right_id)): r for r in reviews}
    if len(indexed) != len(reviews):
        raise ValueError("Duplicate reviews for a market pair")
    matches = []
    now = utcnow()
    for a, b in combinations(sorted(markets, key=lambda m: m.id), 2):
        if a.venue == b.venue or a.mode != b.mode:
            continue
        review = indexed.get(frozenset((a.id, b.id)))
        if review and review.left_id != a.id:
            a, b = b, a

        def normalize(text):
            return " ".join(re.findall(r"\w+", text.casefold()))

        similarity = SequenceMatcher(None, normalize(a.title), normalize(b.title)).ratio()
        comparison = compare_contracts(a, b, contracts.get(a.id), contracts.get(b.id))
        if (
            not review
            and not comparison.same_event
            and (similarity < 0.65 or abs((a.closes_at - b.closes_at).total_seconds()) > 7 * 86400)
        ):
            continue
        status = "candidate"
        reason = "Title similarity only; settlement terms and costs require review."
        if comparison.same_event:
            reason = "Shared structured event; settlement terms and costs require review."
        if review:
            if (review.left_terms_hash, review.right_terms_hash) != (a.terms_hash, b.terms_hash):
                reason = "Settlement terms changed; previous review is invalid."
            elif review.expires_at <= now:
                reason = "Settlement and cost review expired."
            else:
                status, reason = review.status, review.rationale
        if status == "verified" and a.mode == "live":
            if settlement_issues(review, comparison.left, comparison.right):
                status, reason = (
                    "candidate",
                    "Explicit settlement payouts and condition coverage require review.",
                )
            elif comparison.status != "compatible":
                status, reason = "candidate", "Structured settlement comparison is not compatible."
            elif (review.left_definition_hash, review.right_definition_hash) != (
                comparison.left_hash,
                comparison.right_hash,
            ):
                status, reason = "candidate", "Review does not approve the current definitions."
        matches.append(
            Match(
                id=digest([a.mode, *sorted((a.id, b.id))]),
                mode=a.mode,
                left_id=a.id,
                right_id=b.id,
                status=status,
                similarity=round(similarity, 4),
                reason=reason,
                review=review,
                comparison=comparison,
            )
        )
    return matches
