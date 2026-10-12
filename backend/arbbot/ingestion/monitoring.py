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
            progress = await session.get(DiscoveryProgressRecord, key, with_for_update=True)
            offsets = dict(progress.payload) if progress else {}
            rows = (
                await session.scalars(
                    select(MatchRecord)
                    .where(MatchRecord.mode == self.settings.mode, MatchRecord.current.is_(True))
                    .order_by(MatchRecord.id)
                )
            ).all()
            tiers = [[], [], [], [], []]
            for row in rows:
                match = Match.model_validate(row.payload)
                if match.status == "rejected" or any(
                    mid not in indexed for mid in (match.left_id, match.right_id)
                ):
                    continue
                pair = (match.left_id, match.right_id)
                tier = (
                    0
                    if match.status == "verified"
                    else 1
                    if (match.comparison and match.comparison.same_event)
                    else 3
                )
                tiers[tier].append(pair)
            for market in indexed.values():
                tier = 2 if market.external_id in self.watchlists.get(market.venue, ()) else 4
                tiers[tier].append((market.id,))
            selected, counts = set(), {}
            for tier, groups in enumerate(tiers):
                groups.sort()
                offset = int(offsets.get(str(tier), 0)) % max(1, len(groups))
                consumed = 0
                for group in groups[offset:] + groups[:offset]:
                    added = set(group) - selected
                    required = {}
                    for mid in added:
                        venue = indexed[mid].venue
                        required[venue] = required.get(venue, 0) + 1
                    if any(
                        counts.get(v, 0) + n > self.settings.discovery_limit
                        for v, n in required.items()
                    ):
                        continue
                    selected.update(added)
                    for venue, count in required.items():
                        counts[venue] = counts.get(venue, 0) + count
                    consumed += 1
                offsets[str(tier)] = offset + max(1, consumed)
            await session.merge(
                DiscoveryProgressRecord(
                    key=key, mode=self.settings.mode, venue="kalshi", payload=offsets
                )
            )
        return [indexed[mid] for mid in sorted(selected)]
