# Backend fee workstream handoff

## Current status: October 11, 2026

Branch: `backend/completion`; no PR was opened or remote status rechecked during this cleanup.
This update reconciles the local implementation and documented delivery evidence.
See the [roadmap](../implementation-roadmap.md) for the integrated sequence and the [project status handoff](project-status-handoff.md) for the October 11 checks and limitations.
Prior session details and validation evidence are preserved in [history](history/fees-handoff.md).

## Completed

The versioned asynchronous fee contract includes exact inputs, fill ladders, rounding scope, provenance, expiry, and explicit unavailable results.
The Polymarket International fee provider normalizes observed schedules with conservative rounding and recorded regression evidence.
The engine retains reviewed fixed/per-contract fee bounds; the automatic provider path is not connected.

## In progress and blockers

An unfinished Kalshi provider exists locally outside the committed implementation.
A Polymarket US fee policy/provider and account/product-specific applicability remain unfinished.
Recorded fee documents do not establish a complete automatic fee calculation path.
Metadata refresh, depth-dependent provider integration, stale/unknown policy suppression, rounding, and supported slippage validation remain required.

## Next action

Complete and test the Kalshi and Polymarket US fee policies against current official evidence, then connect observed metadata and versioned quotes to depth-dependent sizing.
Keep International policy separate from US policy and block unavailable or stale fees rather than assuming zero.
