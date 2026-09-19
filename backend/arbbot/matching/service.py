import re
from difflib import SequenceMatcher
from itertools import combinations

from arbbot.domain import Market, Match, Review, digest, utcnow


def match_markets(markets: list[Market], reviews: list[Review]) -> list[Match]:
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
        if not review and (similarity < 0.65 or abs((a.closes_at - b.closes_at).days) > 7):
            continue
        status = "candidate"
        reason = "Title similarity only; settlement terms and costs require review."
        if review:
            if (review.left_terms_hash, review.right_terms_hash) != (a.terms_hash, b.terms_hash):
                reason = "Settlement terms changed; previous review is invalid."
            elif review.expires_at <= now:
                reason = "Settlement and cost review expired."
            else:
                status, reason = review.status, review.rationale
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
            )
        )
    return matches
