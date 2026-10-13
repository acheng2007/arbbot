"use client";
import { ModeBadge } from "@/components/data-origin";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { QuoteAge, ValidUntil } from "@/components/freshness";
import {
  formatMoney,
  formatPercent,
  formatPrice,
  formatQuantity,
} from "@/lib/decimal";
import type { Market, Opportunity } from "@/lib/api/schema";
import { venueLabel } from "@/features/shared/status";

export function ClassificationBadge({
  classification,
}: {
  classification: Opportunity["classification"];
}) {
  return classification === "quote_supported_estimate" ? (
    <Badge tone="info">Quote-supported estimate</Badge>
  ) : (
    <Badge tone="caution">Simulated, not quote-supported</Badge>
  );
}

export function LegSummary({
  leg,
  market,
}: {
  leg: Opportunity["legs"][number];
  market?: Market;
}) {
  const asset = market?.settlement_asset ?? "USD";
  return (
    <div className="rounded-lg border border-border p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="neutral">
          {market ? venueLabel(market.venue) : leg.market_id}
        </Badge>
        <Badge tone={leg.outcome === "yes" ? "positive" : "critical"}>
          {leg.native_action === "short_instrument" ? "Short instrument (NO)" : `Buy ${leg.outcome.toUpperCase()}`}
        </Badge>
        <QuoteAge
          sourceAt={leg.source_at ?? (leg.source_timestamp_available ? leg.quote_at : null)}
          receivedAt={leg.received_at ?? leg.quote_at}
        />
      </div>
      <p className="mt-3 text-sm leading-6">{market?.title ?? leg.market_id}</p>
      <dl className="mt-3.5 grid gap-2.5 text-sm sm:grid-cols-2">
        {[
          ["Quantity", formatQuantity(leg.quantity)],
          ["Limit price", formatPrice(leg.limit_price)],
          ...(leg.native_price ? [["Native limit", formatPrice(leg.native_price)]] : []),
          ...(leg.native_action === "short_instrument" ? [
            ["Short proceeds", formatMoney(leg.short_proceeds ?? "0", asset)],
            ["Gross collateral", formatMoney(leg.gross_collateral ?? "0", asset)],
            ["Net buying power", formatMoney(leg.net_buying_power ?? "0", asset)],
          ] : []),
          ["Depth cost", formatMoney(leg.cost_usd, asset)],
          ["Fee bound", formatMoney(leg.fee_bound_usd, asset)],
        ].map(([term, value]) => (
          <div key={term} className="flex justify-between gap-3">
            <dt className="text-muted-foreground">{term}</dt>
            <dd className="tabular-nums">{value}</dd>
          </div>
        ))}
      </dl>
      {leg.fee_policy_id && <details className="mt-3 text-xs text-muted-foreground">
        <summary className="cursor-pointer">Fee policy snapshot</summary>
        <p className="mt-1 break-all font-mono">{leg.fee_policy_id}</p>
      </details>}
      {!leg.source_timestamp_available && (
        <p className="mt-3 text-xs leading-5 text-amber-900">
          This venue supplied no exchange-side timestamp, so the quote age is
          measured from receipt and may understate real latency.
        </p>
      )}
    </div>
  );
}

export function OpportunityCard({
  opportunity,
  markets,
}: {
  opportunity: Opportunity;
  markets: Map<string, Market>;
}) {
  const asset =
    markets.get(opportunity.legs[0].market_id)?.settlement_asset ?? "USD";

  return (
    <article className="rounded-xl border border-border bg-card p-5 sm:p-6">
      <div className="flex flex-wrap items-center gap-2">
        <ClassificationBadge classification={opportunity.classification} />
        <ModeBadge mode={opportunity.mode} feedOrigin={opportunity.feed_origin} />
        <ValidUntil validUntil={opportunity.valid_until} />
        {opportunity.quote_skew_seconds != null && <span className="text-xs text-muted-foreground">
          Quote timing skew {opportunity.quote_skew_seconds.toFixed(3)} seconds
        </span>}
      </div>

      <div className="mt-4 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Net profit after all costs
          </p>
          <p className="mt-1 text-3xl font-semibold tabular-nums">
            {formatMoney(opportunity.net_profit, asset)}
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            {formatPercent(opportunity.return_on_capital)} on{" "}
            {formatMoney(opportunity.capital_required, asset)} capital
          </p>
        </div>
        <Link
          href={`/opportunities/${encodeURIComponent(opportunity.id)}`}
          className="inline-flex items-center gap-1.5 text-sm font-medium text-primary"
        >
          Full calculation and assumptions
          <ArrowRight aria-hidden="true" className="size-4" />
        </Link>
      </div>

      <div className="mt-5 grid gap-4 md:grid-cols-2">
        {opportunity.legs.map((leg) => (
          <LegSummary
            key={`${leg.market_id}-${leg.outcome}`}
            leg={leg}
            market={markets.get(leg.market_id)}
          />
        ))}
      </div>
    </article>
  );
}
