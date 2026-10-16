"""Allocate complete pairs before singles, with durable fair rotation per priority."""

from sqlalchemy import select

from arbbot.domain import Match, utcnow
from arbbot.storage.models import DiscoveryProgressRecord, MatchRecord


class PairMonitor:
    def __init__(self, settings, repository, adapters):
        self.settings, self.repository = settings, repository
        self.watchlists = {
            a.venue: set(getattr(a, "tickers", getattr(a, "market_ids", ()))) for a in adapters
        }

    async def select(self, markets):
        indexed = {m.id: m for m in markets if m.status == "open" and m.closes_at > utcnow()}
        key = f"{self.settings.mode}:pair-monitoring"
        async with self.repository.database.sessions.begin() as session:
            session.info["classification_identity_cache"] = {}
            progress = await session.get(DiscoveryProgressRecord, key, with_for_update=True)
            offsets = dict(progress.payload) if progress else {}
            rows = (
                await session.scalars(
                    select(MatchRecord)
                    .where(MatchRecord.mode == self.settings.mode, MatchRecord.current.is_(True))
                    .order_by(MatchRecord.id)
                )
            ).all()
            tiers = [[], [], [], [], [], []]
            paired = set()
            for row in rows:
                match = Match.model_validate(row.payload)
                if match.qualification is not None:
                    from arbbot.qualification.service import refresh_match

                    match = await refresh_match(session, match)
                if (
                    match.operator_veto
                    or match.relationship == "mismatch"
                    or any(mid not in indexed for mid in (match.left_id, match.right_id))
                ):
                    continue
                from arbbot.matching.classification import configured_state, summary
                from arbbot.storage.models import ClassificationJobRecord

                has_advice = bool(
                    match.classification
                    and (match.classification.run_id or match.classification.supports_candidate)
                )
                job = (
                    await session.get(ClassificationJobRecord, f"{self.settings.mode}:{match.id}")
                    if has_advice or match.ai_only
                    else None
                )
                if job:
                    advice = await summary(session, job)
                    if configured_state(self.settings) != "pending":
                        advice = advice.model_copy(update={"supports_candidate": False})
                    match = match.model_copy(update={"classification": advice})
                if match.ai_only and (
                    not match.classification or not match.classification.supports_candidate
                ):
                    continue
                pair = (match.left_id, match.right_id)
                paired.update(pair)
                watched = any(
                    indexed[mid].external_id in self.watchlists.get(indexed[mid].venue, ())
                    for mid in pair
                )
                tier = (
                    0
                    if match.status == "verified"
                    else 1
                    if (match.comparison and match.comparison.same_event)
                    else 2
                    if watched
                    else 3
                    if match.classification
                    and match.classification.state == "fresh"
                    and match.classification.supports_candidate
                    and match.classification.expires_at
                    and match.classification.expires_at > utcnow()
                    else 4
                )
                tiers[tier].append(pair)
            for market in indexed.values():
                if market.id in paired:
                    continue
                tier = 2 if market.external_id in self.watchlists.get(market.venue, ()) else 5
                tiers[tier].append((market.id,))
            selected, counts = set(), {}

            def allocate(groups, key, caps):
                from collections import defaultdict
                from itertools import zip_longest

                categories = defaultdict(list)
                for group in sorted(groups):
                    categories[indexed[group[0]].category_group].append(group)
                groups = [
                    g
                    for row in zip_longest(*(categories[c] for c in sorted(categories)))
                    for g in row
                    if g is not None
                ]
                offset = int(offsets.get(key, 0)) % max(1, len(groups))
                consumed = 0
                for group in groups[offset:] + groups[:offset]:
                    added = set(group) - selected
                    required = {}
                    for mid in added:
                        venue = indexed[mid].venue
                        required[venue] = required.get(venue, 0) + 1
                    if any(counts.get(v, 0) + n > caps(v) for v, n in required.items()):
                        continue
                    selected.update(added)
                    for venue, count in required.items():
                        counts[venue] = counts.get(venue, 0) + count
                    consumed += 1
                offsets[key] = offset + max(1, consumed)

            exploratory = [group for tier in tiers[3:] for group in tier if len(group) == 2]
            allocate(
                exploratory,
                "exploratory",
                lambda venue: int(
                    self.settings.monitoring_limit(venue)
                    * self.settings.exploratory_monitoring_fraction
                ),
            )
            for tier, groups in enumerate(tiers):
                allocate(groups, str(tier), self.settings.monitoring_limit)
            await session.merge(
                DiscoveryProgressRecord(
                    key=key, mode=self.settings.mode, venue="kalshi", payload=offsets
                )
            )
        return [indexed[mid] for mid in sorted(selected)]
