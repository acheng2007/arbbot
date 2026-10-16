// Recorded fixture dataset used when no backend is configured.
// It is typed against the generated schema so it cannot drift from the API contract.
// Everything here is labeled as fixture data in the interface and must never be
// presented as live exchange data.
import type {
  Book,
  Comparison,
  ContractDefinition,
  CostPolicy,
  Evaluation,
  Extraction,
  Fact,
  Market,
  Match,
  Opportunity,
  Review,
} from "./schema";

/** Deterministic stand-in for a real 64-character terms hash. */
function hash(seed: string) {
  let a = 0x811c9dc5;
  const digits: string[] = [];
  for (let i = 0; i < 64; i += 1) {
    a ^= seed.charCodeAt(i % seed.length) + i;
    a = Math.imul(a, 0x01000193) >>> 0;
    digits.push((a % 16).toString(16));
  }
  return digits.join("");
}

function fact(
  value: string,
  source: Fact["source"],
  quote: string,
  sourceKey?: string,
): Fact {
  return { value, source, quote, source_key: sourceKey ?? null };
}

/**
 * Builds the recorded dataset with timestamps anchored to `now`, so quote ages
 * and freshness states stay demonstrable instead of drifting permanently stale.
 */
export function recordedDataset(now: Date = new Date()) {
  /** ISO timestamp `seconds` before the anchor. */
  const ago = (seconds: number) =>
    new Date(now.getTime() - seconds * 1000).toISOString();
  /** ISO timestamp `seconds` after the anchor. */
  const ahead = (seconds: number) =>
    new Date(now.getTime() + seconds * 1000).toISOString();

  const markets: Market[] = [
    {
      id: "kalshi:CPIYOY-26SEP-T3.0",
      venue: "kalshi",
      external_id: "CPIYOY-26SEP-T3.0",
      mode: "simulation",
      title: "US CPI year-over-year above 3.0% for September 2026",
      rules:
        "This market resolves to Yes if the year-over-year change in the US Consumer Price Index for All Urban Consumers (CPI-U), not seasonally adjusted, for the September 2026 reference month is strictly greater than 3.0 percent, as first published by the Bureau of Labor Statistics. Revisions published after the initial release are disregarded. If the BLS does not publish the September 2026 release on or before 31 October 2026, the market is cancelled and all positions are refunded.",
      closes_at: ahead(22 * 24 * 3600),
      status: "open",
      category_group: "economics",
      category: "Economics",
      settlement_asset: "USD",
      tokens: { yes: "CPIYOY-26SEP-T3.0-YES", no: "CPIYOY-26SEP-T3.0-NO" },
      settlement_details: {
        source: "Bureau of Labor Statistics CPI-U release",
        series: "CUUR0000SA0",
        revision_policy: "initial release only",
        timezone: "America/New_York",
      },
      raw: { ticker: "CPIYOY-26SEP-T3.0", category: "Economics" },
      observed_at: ago(9),
      terms_hash: hash("kalshi-cpi"),
    },
    {
      id: "polymarket:0x8f21",
      venue: "polymarket",
      external_id: "0x8f21a4c7",
      mode: "simulation",
      title: "Will US CPI YoY exceed 3% in September 2026?",
      rules:
        "This market will resolve to Yes if the United States Consumer Price Index for All Urban Consumers (CPI-U), not seasonally adjusted, shows a year-over-year increase above 3.0% for the September 2026 reference month, according to the initial Bureau of Labor Statistics print. Later revisions are ignored. If no release occurs before 1 November 2026 the market resolves 50/50.",
      closes_at: ahead(22 * 24 * 3600),
      status: "open",
      category_group: "economics",
      category: "Economics",
      settlement_asset: "USDC",
      tokens: { yes: "71234...yes", no: "71234...no" },
      settlement_details: {
        source: "BLS CPI-U initial print",
        resolution_source_url: "https://www.bls.gov/cpi/",
        timezone: "UTC",
      },
      raw: { condition_id: "0x8f21a4c7", slug: "us-cpi-yoy-above-3-sep-2026" },
      observed_at: ago(9),
      terms_hash: hash("poly-cpi"),
    },
    {
      id: "kalshi:FEDCUT-26NOV",
      venue: "kalshi",
      external_id: "FEDCUT-26NOV",
      mode: "simulation",
      title: "Fed cuts the target rate at the November 2026 meeting",
      rules:
        "Resolves Yes if the Federal Open Market Committee lowers the midpoint of the federal funds target range at the meeting concluding 5 November 2026, as stated in the FOMC implementation note released that day at 2:00 PM America/New_York. An unscheduled intermeeting cut does not count.",
      closes_at: ahead(45 * 24 * 3600),
      status: "open",
      category_group: "economics",
      category: "Economics",
      settlement_asset: "USD",
      tokens: { yes: "FEDCUT-26NOV-YES", no: "FEDCUT-26NOV-NO" },
      settlement_details: {
        source: "FOMC implementation note",
        timezone: "America/New_York",
        intermeeting_action: "excluded",
      },
      raw: { ticker: "FEDCUT-26NOV", category: "Economics" },
      observed_at: ago(9),
      terms_hash: hash("kalshi-fed"),
    },
    {
      id: "polymarket:0x44b0",
      venue: "polymarket",
      external_id: "0x44b0de19",
      mode: "simulation",
      title: "Fed rate cut in November 2026?",
      rules:
        "Resolves Yes if the Federal Reserve reduces the federal funds target rate at any point during November 2026. Resolution follows the Federal Reserve press release, evaluated in UTC. Intermeeting action counts.",
      closes_at: ahead(70 * 24 * 3600),
      status: "open",
      category_group: "economics",
      category: "Economics",
      settlement_asset: "USDC",
      tokens: { yes: "88120...yes", no: "88120...no" },
      settlement_details: {
        source: "Federal Reserve press release",
        timezone: "UTC",
        intermeeting_action: "included",
      },
      raw: { condition_id: "0x44b0de19", slug: "fed-rate-cut-november-2026" },
      observed_at: ago(9),
      terms_hash: hash("poly-fed"),
    },
    {
      id: "kalshi:PAYROLLS-26OCT-T150",
      venue: "kalshi",
      external_id: "PAYROLLS-26OCT-T150",
      mode: "simulation",
      title: "US nonfarm payrolls above 150k for October 2026",
      rules:
        "Resolves Yes if the initial Bureau of Labor Statistics estimate of the change in total nonfarm payroll employment for October 2026 exceeds 150,000, seasonally adjusted.",
      closes_at: ahead(46 * 24 * 3600),
      status: "open",
      category_group: "economics",
      category: "Economics",
      settlement_asset: "USD",
      tokens: {},
      settlement_details: { source: "BLS Employment Situation" },
      raw: { ticker: "PAYROLLS-26OCT-T150", category: "Economics" },
      observed_at: ago(3 * 3600 + 47 * 60),
      terms_hash: hash("kalshi-nfp"),
    },
    {
      id: "polymarket:0x1d77",
      venue: "polymarket",
      external_id: "0x1d77aa05",
      mode: "simulation",
      title: "NYC high temperature above 90F on 4 July 2026",
      rules:
        "Resolves Yes if the maximum temperature recorded at Central Park (station KNYC) on 4 July 2026 exceeds 90 degrees Fahrenheit according to the National Weather Service daily climate report.",
      closes_at: ago(78 * 24 * 3600),
      status: "closed",
      category_group: "economics",
      category: "Economics",
      settlement_asset: "USDC",
      tokens: { yes: "33019...yes", no: "33019...no" },
      settlement_details: {
        source: "NWS daily climate report",
        station: "KNYC",
      },
      raw: {
        condition_id: "0x1d77aa05",
        slug: "nyc-high-above-90-july-4-2026",
      },
      observed_at: ago(7 * 3600 + 17 * 60),
      terms_hash: hash("poly-temp"),
    },
  ];

  function definition(
    marketId: string,
    seed: string,
    facts: ContractDefinition["facts"],
  ): ContractDefinition {
    return {
      market_id: marketId,
      terms_hash: hash(seed),
      extractor: "rules-parser@0.3.1",
      schema_version: 1,
      facts,
    };
  }

  const kalshiCpiDefinition = definition(
    "kalshi:CPIYOY-26SEP-T3.0",
    "kalshi-cpi",
    {
      event_type: fact(
        "threshold",
        "title",
        "US CPI year-over-year above 3.0%",
      ),
      entity: fact("United States", "title", "US CPI year-over-year"),
      metric: fact(
        "CPI-U year-over-year change",
        "rules",
        "the year-over-year change in the US Consumer Price Index for All Urban Consumers (CPI-U)",
      ),
      measurement: fact(
        "not seasonally adjusted",
        "rules",
        "not seasonally adjusted",
      ),
      reference_period: fact(
        "2026-09",
        "rules",
        "for the September 2026 reference month",
      ),
      source: fact(
        "Bureau of Labor Statistics",
        "settlement_details",
        "Bureau of Labor Statistics CPI-U release",
        "source",
      ),
      value_version: fact(
        "initial release",
        "rules",
        "Revisions published after the initial release are disregarded.",
      ),
      operator: fact(
        "strictly greater than",
        "rules",
        "strictly greater than 3.0 percent",
      ),
      threshold: fact("3.0", "rules", "strictly greater than 3.0 percent"),
      units: fact("percent", "rules", "3.0 percent"),
      timezone: fact(
        "America/New_York",
        "settlement_details",
        "America/New_York",
        "timezone",
      ),
      outcome_orientation: fact("yes on exceed", "title", "above 3.0%"),
      payout: fact(
        "1 USD per contract",
        "settlement_details",
        "settlement_asset USD",
        "source",
      ),
      cancellation: fact(
        "cancel and refund if unpublished by 2026-10-31",
        "rules",
        "the market is cancelled and all positions are refunded",
      ),
    },
  );

  const polyCpiDefinition = definition("polymarket:0x8f21", "poly-cpi", {
    event_type: fact("threshold", "title", "Will US CPI YoY exceed 3%"),
    entity: fact("United States", "title", "US CPI YoY"),
    metric: fact(
      "CPI-U year-over-year change",
      "rules",
      "Consumer Price Index for All Urban Consumers (CPI-U)",
    ),
    measurement: fact(
      "not seasonally adjusted",
      "rules",
      "not seasonally adjusted",
    ),
    reference_period: fact(
      "2026-09",
      "rules",
      "for the September 2026 reference month",
    ),
    source: fact(
      "Bureau of Labor Statistics",
      "settlement_details",
      "BLS CPI-U initial print",
      "source",
    ),
    value_version: fact(
      "initial release",
      "rules",
      "Later revisions are ignored.",
    ),
    operator: fact("strictly greater than", "rules", "increase above 3.0%"),
    threshold: fact("3.0", "rules", "above 3.0%"),
    units: fact("percent", "rules", "3.0%"),
    timezone: fact("UTC", "settlement_details", "UTC", "timezone"),
    outcome_orientation: fact("yes on exceed", "title", "exceed 3%"),
    payout: fact(
      "1 USDC per contract",
      "settlement_details",
      "settlement_asset USDC",
      "source",
    ),
    cancellation: fact(
      "resolve 50/50 if unpublished by 2026-11-01",
      "rules",
      "the market resolves 50/50",
    ),
  });

  const kalshiFedDefinition = definition("kalshi:FEDCUT-26NOV", "kalshi-fed", {
    event_type: fact("policy decision", "title", "Fed cuts the target rate"),
    entity: fact(
      "Federal Open Market Committee",
      "rules",
      "the Federal Open Market Committee",
    ),
    metric: fact(
      "federal funds target range midpoint",
      "rules",
      "the midpoint of the federal funds target range",
    ),
    reference_period: fact(
      "2026-11-05 meeting",
      "rules",
      "the meeting concluding 5 November 2026",
    ),
    source: fact(
      "FOMC implementation note",
      "settlement_details",
      "FOMC implementation note",
      "source",
    ),
    operator: fact("decrease", "rules", "lowers the midpoint"),
    timezone: fact("America/New_York", "rules", "2:00 PM America/New_York"),
    outcome_orientation: fact("yes on cut", "title", "Fed cuts"),
    exceptions: fact(
      "intermeeting cut excluded",
      "rules",
      "An unscheduled intermeeting cut does not count.",
    ),
  });

  const polyFedDefinition = definition("polymarket:0x44b0", "poly-fed", {
    event_type: fact("policy decision", "title", "Fed rate cut"),
    entity: fact("Federal Reserve", "rules", "the Federal Reserve"),
    metric: fact(
      "federal funds target rate",
      "rules",
      "the federal funds target rate",
    ),
    reference_period: fact(
      "2026-11 calendar month",
      "rules",
      "at any point during November 2026",
    ),
    source: fact(
      "Federal Reserve press release",
      "settlement_details",
      "Federal Reserve press release",
      "source",
    ),
    operator: fact(
      "decrease",
      "rules",
      "reduces the federal funds target rate",
    ),
    timezone: fact("UTC", "rules", "evaluated in UTC"),
    outcome_orientation: fact("yes on cut", "title", "rate cut"),
    exceptions: fact(
      "intermeeting action included",
      "rules",
      "Intermeeting action counts.",
    ),
  });

  const extractions: Record<string, Extraction> = {
    "kalshi:CPIYOY-26SEP-T3.0": {
      status: "partial",
      definition: kalshiCpiDefinition,
      missing_fields: ["observation_window", "exceptions"],
      issues: [
        "No explicit observation window; assumed the full reference month.",
      ],
    },
    "polymarket:0x8f21": {
      status: "partial",
      definition: polyCpiDefinition,
      missing_fields: ["observation_window", "exceptions"],
      issues: [
        "Cancellation differs from the paired venue: 50/50 resolution rather than a refund.",
      ],
    },
    "kalshi:FEDCUT-26NOV": {
      status: "partial",
      definition: kalshiFedDefinition,
      missing_fields: [
        "measurement",
        "threshold",
        "units",
        "value_version",
        "observation_window",
        "payout",
        "cancellation",
      ],
      issues: ["Cancellation terms are not stated in the published rules."],
    },
    "polymarket:0x44b0": {
      status: "ambiguous",
      definition: polyFedDefinition,
      missing_fields: [
        "measurement",
        "threshold",
        "units",
        "value_version",
        "observation_window",
        "payout",
        "cancellation",
      ],
      issues: [
        "The resolution window is a calendar month rather than a single meeting.",
        "Intermeeting action is included, which the paired contract excludes.",
      ],
    },
    "kalshi:PAYROLLS-26OCT-T150": {
      status: "unsupported",
      definition: definition("kalshi:PAYROLLS-26OCT-T150", "kalshi-nfp", {
        event_type: fact(
          "threshold",
          "title",
          "US nonfarm payrolls above 150k",
        ),
        entity: fact("United States", "title", "US nonfarm payrolls"),
        metric: fact(
          "change in total nonfarm payroll employment",
          "rules",
          "the change in total nonfarm payroll employment",
        ),
        threshold: fact("150000", "rules", "exceeds 150,000"),
      }),
      missing_fields: [
        "source",
        "timezone",
        "cancellation",
        "payout",
        "observation_window",
        "value_version",
        "units",
        "outcome_orientation",
        "operator",
        "measurement",
        "reference_period",
        "exceptions",
      ],
      issues: ["No counterpart contract has been discovered on another venue."],
    },
  };

  const books: Record<string, Book> = {
    "kalshi:CPIYOY-26SEP-T3.0": {
      market_id: "kalshi:CPIYOY-26SEP-T3.0",
      mode: "simulation",
      yes_asks: [
        { price: "0.43", size: "250" },
        { price: "0.44", size: "400" },
        { price: "0.46", size: "1200" },
      ],
      no_asks: [
        { price: "0.56", size: "310" },
        { price: "0.58", size: "900" },
      ],
      min_order_size: "1",
      source_at: ago(12),
      received_at: ago(9),
      raw: { ticker: "CPIYOY-26SEP-T3.0" },
    },
    "polymarket:0x8f21": {
      market_id: "polymarket:0x8f21",
      mode: "simulation",
      yes_asks: [
        { price: "0.45", size: "800" },
        { price: "0.47", size: "1500" },
      ],
      no_asks: [
        { price: "0.53", size: "620" },
        { price: "0.55", size: "1800" },
      ],
      min_order_size: "5",
      // Polymarket does not supply an exchange-side timestamp in this recording.
      source_at: null,
      received_at: ago(10),
      raw: { condition_id: "0x8f21a4c7" },
    },
    "kalshi:FEDCUT-26NOV": {
      market_id: "kalshi:FEDCUT-26NOV",
      mode: "simulation",
      yes_asks: [{ price: "0.71", size: "150" }],
      no_asks: [{ price: "0.30", size: "220" }],
      min_order_size: "1",
      source_at: ago(41),
      received_at: ago(38),
      raw: { ticker: "FEDCUT-26NOV" },
    },
    "polymarket:0x44b0": {
      market_id: "polymarket:0x44b0",
      mode: "simulation",
      yes_asks: [{ price: "0.68", size: "900" }],
      no_asks: [{ price: "0.33", size: "700" }],
      min_order_size: "5",
      source_at: null,
      received_at: ago(36),
      raw: { condition_id: "0x44b0de19" },
    },
    "kalshi:PAYROLLS-26OCT-T150": {
      market_id: "kalshi:PAYROLLS-26OCT-T150",
      mode: "simulation",
      yes_asks: [],
      no_asks: [],
      min_order_size: "1",
      source_at: null,
      // Recorded well before the other books so the interface can show a stale quote.
      received_at: ago(3 * 3600 + 47 * 60),
      raw: { ticker: "PAYROLLS-26OCT-T150" },
    },
    "polymarket:0x1d77": {
      market_id: "polymarket:0x1d77",
      mode: "simulation",
      yes_asks: [],
      no_asks: [],
      min_order_size: "5",
      source_at: null,
      received_at: ago(7 * 3600 + 17 * 60),
      raw: { condition_id: "0x1d77aa05" },
    },
  };

  const cpiComparison: Comparison = {
    status: "compatible",
    same_event: true,
    event_key: "us-cpi-yoy-2026-09-gt-3.0",
    left: kalshiCpiDefinition,
    right: polyCpiDefinition,
    left_hash: kalshiCpiDefinition.terms_hash,
    right_hash: polyCpiDefinition.terms_hash,
    differences: [
      {
        field: "metric",
        status: "equal",
        left: "CPI-U year-over-year change",
        right: "CPI-U year-over-year change",
      },
      {
        field: "measurement",
        status: "equal",
        left: "not seasonally adjusted",
        right: "not seasonally adjusted",
      },
      {
        field: "reference_period",
        status: "equal",
        left: "2026-09",
        right: "2026-09",
      },
      {
        field: "operator",
        status: "equal",
        left: "strictly greater than",
        right: "strictly greater than",
      },
      { field: "threshold", status: "equal", left: "3.0", right: "3.0" },
      {
        field: "value_version",
        status: "equal",
        left: "initial release",
        right: "initial release",
      },
      {
        field: "timezone",
        status: "different",
        left: "America/New_York",
        right: "UTC",
      },
      {
        field: "cancellation",
        status: "different",
        left: "cancel and refund if unpublished by 2026-10-31",
        right: "resolve 50/50 if unpublished by 2026-11-01",
      },
      {
        field: "observation_window",
        status: "unknown",
        left: null,
        right: null,
      },
      { field: "exceptions", status: "unknown", left: null, right: null },
    ],
    issues: [
      "Cancellation handling differs: one venue refunds and the other resolves 50/50, which changes the payoff if the release is delayed.",
      "The stated timezones differ, though both reference the same BLS release.",
    ],
  };

  const fedComparison: Comparison = {
    status: "conflict",
    same_event: false,
    event_key: null,
    left: kalshiFedDefinition,
    right: polyFedDefinition,
    left_hash: kalshiFedDefinition.terms_hash,
    right_hash: polyFedDefinition.terms_hash,
    differences: [
      {
        field: "entity",
        status: "different",
        left: "Federal Open Market Committee",
        right: "Federal Reserve",
      },
      {
        field: "metric",
        status: "different",
        left: "federal funds target range midpoint",
        right: "federal funds target rate",
      },
      {
        field: "reference_period",
        status: "different",
        left: "2026-11-05 meeting",
        right: "2026-11 calendar month",
      },
      {
        field: "source",
        status: "different",
        left: "FOMC implementation note",
        right: "Federal Reserve press release",
      },
      {
        field: "operator",
        status: "equal",
        left: "decrease",
        right: "decrease",
      },
      {
        field: "timezone",
        status: "different",
        left: "America/New_York",
        right: "UTC",
      },
      {
        field: "exceptions",
        status: "different",
        left: "intermeeting cut excluded",
        right: "intermeeting action included",
      },
      { field: "cancellation", status: "unknown", left: null, right: null },
    ],
    issues: [
      "One contract settles on a single scheduled meeting; the other settles on any November action.",
      "Intermeeting cuts settle these contracts differently, so the payoffs can diverge.",
    ],
  };

  const payrollsComparison: Comparison = {
    status: "incomplete",
    same_event: false,
    event_key: null,
    left: extractions["kalshi:PAYROLLS-26OCT-T150"].definition,
    right: null,
    left_hash: extractions["kalshi:PAYROLLS-26OCT-T150"].definition.terms_hash,
    right_hash: null,
    differences: [
      {
        field: "source",
        status: "unknown",
        left: "Bureau of Labor Statistics",
        right: null,
      },
      { field: "timezone", status: "unknown", left: null, right: null },
      { field: "cancellation", status: "unknown", left: null, right: null },
    ],
    issues: [
      "No counterpart definition was extracted, so equivalence cannot be assessed.",
    ],
  };

  function costs(overrides: Partial<CostPolicy>): CostPolicy {
    return {
      fee_per_contract: "0.01",
      fixed_fee: "0",
      min_order_size: "1",
      min_notional: "1",
      cost_fx: "1",
      payout_fx: "1",
      evidence: "Published venue fee schedule reviewed on 2026-09-18.",
      ...overrides,
    };
  }

  const cpiReview: Review = {
    left_id: "kalshi:CPIYOY-26SEP-T3.0",
    right_id: "polymarket:0x8f21",
    left_terms_hash: hash("kalshi-cpi"),
    right_terms_hash: hash("poly-cpi"),
    left_definition_hash: kalshiCpiDefinition.terms_hash,
    right_definition_hash: polyCpiDefinition.terms_hash,
    status: "verified",
    reviewer: "fixture-reviewer",
    rationale:
      "Both contracts settle on the initial, not seasonally adjusted BLS CPI-U year-over-year print for the September 2026 reference month with the same strict 3.0 percent threshold. The residual cancellation difference is recorded as an accepted risk rather than an equivalence.",
    resolution_sources:
      "Bureau of Labor Statistics CPI-U release, series CUUR0000SA0, initial publication only.",
    deadlines_and_timezones:
      "The BLS release is a single fixed publication; the stated America/New_York and UTC references resolve to the same instant.",
    cancellation_and_exceptions:
      "If the release slips past 31 October 2026, the Kalshi contract refunds while the Polymarket contract resolves 50/50. That divergence is an explicit residual risk of this pairing.",
    expires_at: ahead(10 * 24 * 3600),
    scenarios: [
      { name: "CPI above 3.0%", left_yes: "1", right_yes: "1" },
      { name: "CPI at or below 3.0%", left_yes: "0", right_yes: "0" },
    ],
    left_costs: costs({ fee_per_contract: "0.01" }),
    right_costs: costs({
      fee_per_contract: "0.02",
      min_order_size: "5",
      min_notional: "5",
    }),
  };

  const rejectedReview: Review = {
    left_id: "kalshi:FEDCUT-26NOV",
    right_id: "polymarket:0x44b0",
    left_terms_hash: hash("kalshi-fed"),
    right_terms_hash: hash("poly-fed"),
    left_definition_hash: kalshiFedDefinition.terms_hash,
    right_definition_hash: polyFedDefinition.terms_hash,
    status: "rejected",
    reviewer: "fixture-reviewer",
    rationale:
      "An intermeeting cut in November 2026 settles the Polymarket contract Yes and the Kalshi contract No, so the payoffs are not equivalent across all settlement outcomes.",
    resolution_sources:
      "FOMC implementation note compared against the broader Federal Reserve press release feed.",
    deadlines_and_timezones:
      "One contract is fixed to the 5 November 2026 meeting; the other spans the whole calendar month in UTC.",
    cancellation_and_exceptions:
      "Neither venue publishes cancellation terms for this event, so a delayed or cancelled meeting is unmodelled.",
    expires_at: ahead(24 * 24 * 3600),
    scenarios: [
      { name: "Cut at the November meeting", left_yes: "1", right_yes: "1" },
      { name: "Intermeeting cut only", left_yes: "0", right_yes: "1" },
      { name: "No cut in November", left_yes: "0", right_yes: "0" },
    ],
    left_costs: costs({}),
    right_costs: costs({
      fee_per_contract: "0.02",
      min_order_size: "5",
      min_notional: "5",
    }),
  };

  const matches: Match[] = [
    {
      id: "match-cpi-2026-09",
      mode: "simulation",
      left_id: "kalshi:CPIYOY-26SEP-T3.0",
      right_id: "polymarket:0x8f21",
      status: "verified",
      relationship: "verified",
      operator_veto: false,
      similarity: 0.94,
      reason:
        "Identical metric, reference period, threshold and revision policy; reviewed and approved with a recorded cancellation caveat.",
      review: cpiReview,
      comparison: cpiComparison,
    },
    {
      id: "match-fed-2026-11",
      mode: "simulation",
      left_id: "kalshi:FEDCUT-26NOV",
      right_id: "polymarket:0x44b0",
      status: "rejected",
      relationship: "mismatch",
      operator_veto: true,
      similarity: 0.88,
      reason:
        "High title similarity, but the settlement windows and intermeeting handling diverge.",
      review: rejectedReview,
      comparison: fedComparison,
    },
    {
      id: "match-payrolls-2026-10",
      mode: "simulation",
      left_id: "kalshi:PAYROLLS-26OCT-T150",
      right_id: "polymarket:0x1d77",
      status: "candidate",
      relationship: "unverified",
      operator_veto: false,
      similarity: 0.21,
      reason:
        "Proposed by the discovery pass only; no counterpart definition has been extracted yet.",
      review: null,
      comparison: payrollsComparison,
    },
  ];

  const opportunities: Opportunity[] = [
    {
      id: "opp-cpi-2026-09-01",
      match_id: "match-cpi-2026-09",
      mode: "simulation",
      classification: "quote_supported_estimate",
      evaluated_at: ago(8),
      valid_until: ahead(22),
      quantity: "250",
      legs: [
        {
          market_id: "kalshi:CPIYOY-26SEP-T3.0",
          outcome: "yes",
          quantity: "250",
          limit_price: "0.43",
          book_id: "book-kalshi-cpi-8841",
          quote_at: ago(12),
          source_timestamp_available: true,
          native_cost: "107.50",
          cost_usd: "107.50",
          fee_bound_usd: "2.50",
        },
        {
          market_id: "polymarket:0x8f21",
          outcome: "no",
          quantity: "250",
          limit_price: "0.53",
          book_id: "book-poly-cpi-2290",
          quote_at: ago(10),
          source_timestamp_available: false,
          native_cost: "132.50",
          cost_usd: "132.50",
          fee_bound_usd: "5.00",
        },
      ],
      capital_required: "247.50",
      estimated_outlay: "240.00",
      fee_bound: "7.50",
      slippage_reserve: "0.24",
      minimum_payout: "250.00",
      net_profit: "2.26",
      return_on_capital: "0.0091",
      scenario_payouts: {
        "CPI above 3.0%": "2.26",
        "CPI at or below 3.0%": "2.26",
      },
      review: cpiReview,
      comparison: cpiComparison,
      assumptions: [
        "Both legs fill at the quoted top-of-book prices for the full 250 contracts.",
        "Balances are already funded on both venues; no transfer time is modelled.",
        "The Polymarket book carries no exchange-side timestamp, so its age is measured from receipt.",
        "A delayed BLS release settles the two contracts differently and is not covered by this estimate.",
      ],
    },
  ];

  const history: Opportunity[] = [
    {
      ...opportunities[0],
      id: "opp-cpi-2026-09-00",
      evaluated_at: ago(17 * 60 + 11),
      valid_until: ago(16 * 60 + 41),
      quantity: "100",
      capital_required: "99.00",
      estimated_outlay: "96.00",
      fee_bound: "3.00",
      slippage_reserve: "0.10",
      minimum_payout: "100.00",
      net_profit: "0.90",
      return_on_capital: "0.0091",
      scenario_payouts: {
        "CPI above 3.0%": "0.90",
        "CPI at or below 3.0%": "0.90",
      },
    },
  ];

  const evaluations: Evaluation[] = [
    {
      match_id: "match-cpi-2026-09",
      mode: "simulation",
      evaluated_at: ago(8),
      blocked_reasons: [],
      opportunities,
    },
    {
      match_id: "match-fed-2026-11",
      mode: "simulation",
      evaluated_at: ago(35),
      blocked_reasons: [
        "The pair was rejected in review; settlement is not equivalent across all outcomes.",
      ],
      opportunities: [],
    },
    {
      match_id: "match-payrolls-2026-10",
      mode: "simulation",
      evaluated_at: ago(35),
      blocked_reasons: [
        "No verified review exists for this candidate pair.",
        "No executable quotes are available on either venue.",
      ],
      opportunities: [],
    },
  ];

  return {
    markets,
    extractions,
    books,
    matches,
    opportunities,
    history,
    evaluations,
  };
}

export type RecordedDataset = ReturnType<typeof recordedDataset>;
