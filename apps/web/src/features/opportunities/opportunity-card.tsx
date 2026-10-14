"use client";
import { Disclosure } from "@/components/disclosure";
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
          {leg.native_action === "short_instrument"
            ? "Short instrument (NO)"
            : `Buy ${leg.outcome.toUpperCase()}`}
        </Badge>
        <QuoteAge
          sourceAt={
            leg.source_at ??
            (leg.source_timestamp_available ? leg.quote_at : null)
          }
          receivedAt={leg.received_at ?? leg.quote_at}
          compact
        />
      </div>
      <p className="mt-3 text-sm leading-6">{market?.title ?? leg.market_id}</p>
      <p className="my-3 text-sm">
        {formatQuantity(leg.quantity)} contracts ·{" "}
        {leg.native_action === "short_instrument"
          ? "Short collateral"
          : "Limit"}{" "}
        {formatPrice(leg.limit_price)}
      </p>
      <Disclosure title="Leg costs and quote assumptions">
        <dl className="mt-3.5 grid gap-2.5 text-sm sm:grid-cols-2">
          {[
            ["Quantity", formatQuantity(leg.quantity)],
            ["Limit price", formatPrice(leg.limit_price)],
            ...(leg.native_price
              ? [["Native limit", formatPrice(leg.native_price)]]
              : []),
            ...(leg.native_action === "short_instrument"
              ? [
                  [
                    "Short proceeds",
                    formatMoney(leg.short_proceeds ?? "0", asset),
                  ],
                  [
                    "Gross collateral",
                    formatMoney(leg.gross_collateral ?? "0", asset),
                  ],
                  [
                    "Net buying power",
                    formatMoney(leg.net_buying_power ?? "0", asset),
                  ],
                ]
              : []),
            ["Depth cost", formatMoney(leg.cost_usd, asset)],
            ["Fee bound", formatMoney(leg.fee_bound_usd, asset)],
          ].map(([term, value]) => (
            <div key={term} className="flex justify-between gap-3">
              <dt className="text-muted-foreground">{term}</dt>
              <dd className="tabular-nums">{value}</dd>
            </div>
          ))}
        </dl>
        {leg.fee_policy_id && (
          <details className="mt-3 text-xs text-muted-foreground">
            <summary className="cursor-pointer">Fee policy snapshot</summary>
            <p className="mt-1 break-all font-mono">{leg.fee_policy_id}</p>
          </details>
        )}
        {!leg.source_timestamp_available && (
          <p className="mt-3 text-xs leading-5 text-amber-900">
            This venue supplied no exchange-side timestamp, so the quote age is
            measured from receipt and may understate real latency.
          </p>
        )}
      </Disclosure>
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
    <article className="rounded-xl border border-border bg-card p-4 sm:p-5">
      <div className="flex flex-wrap items-center gap-2">
        <ModeBadge
          mode={opportunity.mode}
          feedOrigin={opportunity.feed_origin}
        />
        <ValidUntil validUntil={opportunity.valid_until} />
        {opportunity.classification !== "quote_supported_estimate" && (
          <ClassificationBadge classification={opportunity.classification} />
        )}
      </div>
      <h2 className="mt-3 text-lg font-semibold">
        <Link
          href={`/opportunities/${encodeURIComponent(opportunity.id)}`}
          className="hover:text-primary"
        >
          {markets.get(opportunity.legs[0].market_id)?.title ??
            "Cross-exchange opportunity"}
        </Link>
      </h2>
      <div className="mt-4 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs text-muted-foreground">Estimated net profit</p>
          <p className="text-3xl font-semibold tabular-nums text-primary">
            {formatMoney(opportunity.net_profit, asset)}
          </p>
        </div>
        <dl className="flex flex-wrap gap-5 text-sm">
          {[
            ["Return", formatPercent(opportunity.return_on_capital)],
            ["Capital", formatMoney(opportunity.capital_required, asset)],
            ["Size", `${formatQuantity(opportunity.quantity)} contracts`],
          ].map(([label, value]) => (
            <div key={label}>
              <dt className="text-xs text-muted-foreground">{label}</dt>
              <dd className="mt-1 font-semibold tabular-nums">{value}</dd>
            </div>
          ))}
        </dl>
      </div>
      <div className="mt-4 space-y-2 border-t border-border pt-3">
        {opportunity.legs.map((leg) => (
          <div
            key={`${leg.market_id}:${leg.outcome}`}
            className="flex flex-wrap items-center justify-between gap-2 text-sm"
          >
            <span>
              {venueLabel(markets.get(leg.market_id)?.venue ?? "Unknown venue")}{" "}
              ·{" "}
              {leg.native_action === "short_instrument"
                ? "Short YES (NO)"
                : `Buy ${leg.outcome.toUpperCase()}`}{" "}
              <strong>
                {leg.native_action === "short_instrument" ? "Collateral " : ""}
                {formatPrice(leg.limit_price)}
              </strong>
            </span>
            <QuoteAge
              sourceAt={
                leg.source_at ??
                (leg.source_timestamp_available ? leg.quote_at : null)
              }
              receivedAt={leg.received_at ?? leg.quote_at}
              compact
            />
          </div>
        ))}
      </div>
      <Link
        href={`/opportunities/${encodeURIComponent(opportunity.id)}`}
        className="mt-4 inline-flex items-center gap-2 text-xs font-semibold text-primary"
      >
        View calculation and assumptions
        <ArrowRight aria-hidden="true" className="size-3" />
      </Link>
    </article>
  );
}
