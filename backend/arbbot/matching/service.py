import re
from collections import defaultdict
from difflib import SequenceMatcher
from itertools import combinations

from arbbot.domain import Market, Match, Review, digest, utcnow
from arbbot.matching.contracts import EVENT_FIELDS, ContractDefinition, compare_contracts
from arbbot.matching.settlement import settlement_issues


def match_markets(
    markets: list[Market],
    reviews: list[Review],
    definitions: list[ContractDefinition] | None = None,
    classifications=None,
    reviewed_pairs=None,
) -> list[Match]:
    contracts = {d.market_id: d for d in definitions or []}
    if len(contracts) != len(definitions or []):
        raise ValueError("Duplicate contract definitions for a market")
    indexed = {frozenset((r.left_id, r.right_id)): r for r in reviews}
    if len(indexed) != len(reviews):
        raise ValueError("Duplicate reviews for a market pair")
    matches = []
    now = utcnow()
    classifications = classifications or {}
    reviewed_keys = {frozenset((r.left_id, r.right_id)) for r in reviewed_pairs or []}
    pairs, limited = retrieve_candidates(
        markets,
        contracts,
        reviewed_pairs if reviewed_pairs is not None else reviews,
        supplement=20 if classifications else 0,
    )
    for a, b in pairs:
        if a.venue == b.venue or a.mode != b.mode:
            continue
        pair_key = frozenset((a.id, b.id))
        review = indexed.get(pair_key)
        retrieved_review = pair_key in reviewed_keys
        if review and review.left_id != a.id:
            a, b = b, a

        def normalize(text):
            return " ".join(re.findall(r"\w+", text.casefold()))

        similarity = SequenceMatcher(None, normalize(a.title), normalize(b.title)).ratio()
        comparison = compare_contracts(a, b, contracts.get(a.id), contracts.get(b.id))
        advice = classifications.get(digest([a.mode, *sorted((a.id, b.id))]))
        supported = bool(advice and advice.state == "fresh" and advice.supports_candidate)
        periods = [
            contracts.get(m.id).facts.get("reference_period") if contracts.get(m.id) else None
            for m in (a, b)
        ]
        if all(periods) and periods[0].value != periods[1].value:
            supported = False
        deterministic = bool(
            review
            or retrieved_review
            or comparison.same_event
            or (
                similarity >= 0.65 and abs((a.closes_at - b.closes_at).total_seconds()) <= 7 * 86400
            )
        )
        if (
            not supported
            and not review
            and not retrieved_review
            and not comparison.same_event
            and (similarity < 0.65 or abs((a.closes_at - b.closes_at).total_seconds()) > 7 * 86400)
        ):
            continue
        status = "candidate"
        reason = (
            "AI suggests the same event; settlement terms and costs require review."
            if supported and not deterministic
            else "Title similarity only; settlement terms and costs require review."
        )
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
                classification=advice,
                ai_only=not deterministic,
                feed_origin=a.feed_origin if a.feed_origin != "exchange" else b.feed_origin,
                id=digest([a.mode, *sorted((a.id, b.id))]),
                mode=a.mode,
                left_id=a.id,
                right_id=b.id,
                status=status,
                similarity=round(similarity, 4),
                retrieval_limited=a.id in limited or b.id in limited,
                retrieval_limit=100,
                reason=reason,
                review=review,
                comparison=comparison,
            )
        )
    return matches


STOPWORDS = frozenset(
    "will the a an is be in of at to for and or on by this that win yes no market".split()
)


def retrieve_candidates(markets, contracts, reviews, limit=100, supplement=0):
    """Exact structured keys first, then bounded inverted-index title hypotheses."""
    indexed = {market.id: market for market in markets}
    groups, postings = defaultdict(list), defaultdict(set)
    tokens_by_market = {}
    for market in markets:
        definition = contracts.get(market.id)
        values = tuple(
            definition.facts.get(name).value
            if definition and definition.facts.get(name)
            else "unknown"
            for name in EVENT_FIELDS
        )
        if "unknown" not in values:
            groups[(market.mode, values)].append(market.id)
        tokens = {
            token
            for token in re.findall(r"\w+", market.title.casefold())
            if len(token) > 2 and token not in STOPWORDS
        }
        tokens_by_market[market.id] = tokens
        for token in tokens:
            postings[(market.mode, token)].add(market.id)
    keys, limited = set(), set()
    for group in groups.values():
        for left, right in combinations(sorted(group), 2):
            if indexed[left].venue != indexed[right].venue:
                keys.add((left, right))
    for review in reviews:
        if review.left_id in indexed and review.right_id in indexed:
            keys.add(tuple(sorted((review.left_id, review.right_id))))
    for market in sorted(markets, key=lambda m: m.id):
        tokens = tokens_by_market[market.id]
        # The rarest terms provide bounded retrieval even in a broad sports catalog.
        selected = sorted(tokens, key=lambda token: (len(postings[(market.mode, token)]), token))[
            :8
        ]
        scores = defaultdict(int)
        for token in selected:
            for other_id in postings[(market.mode, token)]:
                other = indexed[other_id]
                if (
                    other.venue == market.venue
                    or abs((other.closes_at - market.closes_at).total_seconds()) > 7 * 86400
                ):
                    continue
                if (
                    market.category
                    and other.category
                    and market.category.casefold() != other.category.casefold()
                ):
                    continue
                scores[other_id] += 1
        ordered = sorted(scores, key=lambda identifier: (-scores[identifier], identifier))
        if len(ordered) > limit:
            limited.add(market.id)
        for other_id in ordered[:limit]:
            keys.add(tuple(sorted((market.id, other_id))))
    if supplement:
        extras = set()
        for market in sorted(markets, key=lambda m: m.id):
            category = " ".join(re.findall(r"\w+", (market.category or "").casefold()))
            nearby = sorted(
                (
                    other
                    for other in markets
                    if other.venue != market.venue
                    and other.mode == market.mode
                    and abs((other.closes_at - market.closes_at).total_seconds()) <= 7 * 86400
                    and category
                    and category == " ".join(re.findall(r"\w+", (other.category or "").casefold()))
                ),
                key=lambda other: (
                    abs((other.closes_at - market.closes_at).total_seconds()),
                    other.id,
                ),
            )
            if len(nearby) > supplement:
                limited.add(market.id)
            for other in nearby[:supplement]:
                pair = tuple(sorted((market.id, other.id)))
                if pair not in keys:
                    extras.add(pair)
        counts = defaultdict(int)
        for left, right in sorted(
            extras,
            key=lambda pair: (
                abs((indexed[pair[0]].closes_at - indexed[pair[1]].closes_at).total_seconds()),
                pair,
            ),
        ):
            if counts[left] >= supplement or counts[right] >= supplement:
                limited.update((left, right))
                continue
            counts[left] += 1
            counts[right] += 1
            keys.add((left, right))
    return [(indexed[left], indexed[right]) for left, right in sorted(keys)], limited
