# Recorded contract validation

The initial corpus is in `backend/tests/fixtures/contracts/recorded.json`.
It contains nine public market metadata responses fetched directly from Kalshi and Polymarket, with source URLs and UTC capture timestamps.
No order books, credentials, private account data, or synthetic prices are included.
Historical capture values are evidence for testing, not current trading data.

`labels.json` contains independently read canonical facts, eligibility expectations, notes, and a SHA-256 digest of each captured payload.
Digests use the application's canonical JSON encoding.
The labels are deliberately partial and do not approve settlement equivalence.
They distinguish headline/core CPI, annual/monthly measurements, CPI/PCE, jurisdiction, and different reporting months.
Source quotations are checked against the preserved market text when an extractor proposes a fact.

## Reproduce the report

```sh
.venv/bin/python -m arbbot.matching.corpus report \
  --records backend/tests/fixtures/contracts/recorded.json \
  --labels backend/tests/fixtures/contracts/labels.json
.venv/bin/pytest -q backend/tests/test_recorded_contracts.py
```

The report lists correct fields, missing labeled fields, unexpected or incorrect fields, adapter eligibility, and extraction issues for each market.
The command exits nonzero on incorrect extracted fields.
Missing fields remain visible even when the regression tests pass.
The replay tests cover response normalization, discovery exclusion, source evidence, persistence, and the extraction REST endpoint without calling the exchanges.
There is no frontend yet, so this is backend integration coverage rather than a browser test.

The initial parser baseline was zero of 63 labeled fields extracted.
Version `us-cpi-rules/v2` extracts 14 fields from the two recorded Kalshi contracts, with zero incorrect fields in this corpus.
It recognizes their explicit primary-rule grammar without inferring US jurisdiction, seasonal adjustment, or source publisher from a ticker.
A reporting month is taken from the conditional rule, not the later publication date.
These partial definitions cannot pass the live approval gate.

Six Polymarket inflation-related fixtures have `negRisk=true` and are deliberately rejected by the current live discovery adapter.
The corpus includes them to expose product coverage gaps and misleadingly similar contracts, not to override that exclusion.
The remaining supported Polymarket fixture is a Treasury yield contract unrelated to CPI.
There is no verified positive cross-exchange pair in this initial corpus.

## Add new recordings

Use explicit market IDs and a new output file:

```sh
.venv/bin/python -m arbbot.matching.corpus record \
  kalshi:KXCPI-26OCT-T1.0 polymarket:4469383 \
  --output /tmp/arbbot-new-contracts.json
```

Recording makes paced public metadata requests and refuses to overwrite an existing file.
The recorder does not subscribe to prices, authenticate, approve contracts, or place orders.
Review the captured rules and metadata, independently label the relevant facts, and add regression cases before expanding supported extraction grammar.
Do not regenerate labels from extractor output.
Do not relabel an excluded contract as supported to make a test pass.

The response adapters follow the documented [Kalshi markets API](https://docs.kalshi.com/api-reference/market/get-markets) and [Polymarket markets API](https://docs.polymarket.com/api-reference/markets/list-markets).
The next evidence needed is Kalshi series/source documentation and a supported overlapping cross-exchange event.

## CI

`.github/workflows/backend.yml` runs backend lint, formatting, SQLite and PostgreSQL tests, migrations, the corpus report, and generated-schema drift checks.
Tests replay recordings and do not depend on live exchange availability.
The workflow definition has been checked through local equivalent commands; a hosted run remains pending until the workflow is pushed.
