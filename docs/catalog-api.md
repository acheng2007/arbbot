# Catalog search and filtering

`GET /api/v1/markets` retains its list response and defaults of `limit=100`, `offset=0`, ordered by market ID.
It accepts `venue=kalshi|polymarket`, `status=open|closed`, `family`, and `q`.
`GET /api/v1/matches` retains its list response and defaults, ordered by match ID, and includes only current matches.
It accepts `venue`, `status=candidate|verified|rejected`, `family`, `q`, and `evidence=complete|incomplete`.
Both endpoints require `limit` from 1 to 200 and `offset` from 0 to 100000.
Search text is limited to 200 characters and family to 100.

Filters combine with AND and execute in SQL before ordering, offset, and limit.
Text search is a case-insensitive literal substring of market ID, title, or rules.
Percent signs, underscores, and the escape character are escaped as literals rather than SQL wildcard syntax.
All user-supplied values are bound parameters.
Mode always comes from the server configuration; callers cannot select another mode through filters.
For matches, venue/family/text predicates must all match the same leg.
An EXISTS subquery prevents duplicated pairs when both legs match.
Stable ordering applies to a fixed catalog; offset pages are not a transaction snapshot across concurrent ingestion cycles.

Family is the existing deterministic extractor's known metric, currently `cpi` or `core_cpi` where language supports it.
It is a browsing label and establishes no settlement equivalence.
No metric fact means an unknown family, stored as NULL and excluded from explicit family filters.
The projection refreshes when an accepted market update is persisted; older updates cannot overwrite it.
This necessary repository integration permits indexed SQL filtering rather than parsing or filtering after pagination.

Complete evidence means both definitions are present, the comparison reports no evidence issues, and all comparison differences are known.
Complete evidence can still conflict and does not imply human approval, executable quotes, or profitability.
The evidence flag updates atomically with the published match payload.
Old or absent comparison data conservatively remains incomplete.

Apply the additive catalog migration before starting this application revision.
Existing records start with unknown families and incomplete evidence until the next normal ingestion/publication cycle refreshes them.
This avoids guessing classifications or rewriting financial audit payloads during migration.
The `(mode, family, id)` index supports family filtering and deterministic pagination.
SQLite and PostgreSQL query-plan tests verify index eligibility; they are not production latency benchmarks.
Text searches remain bounded API queries over the mode's catalog and have no dedicated full-text index in this increment.

Examples:

```text
/api/v1/markets?venue=kalshi&status=open&family=cpi&limit=50
/api/v1/markets?q=August%202026
/api/v1/matches?status=candidate&evidence=incomplete
/api/v1/matches?family=cpi&evidence=complete&limit=50&offset=50
```
