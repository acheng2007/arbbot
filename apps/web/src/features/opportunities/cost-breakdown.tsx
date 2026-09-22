"use client";
import {
  formatMoney,
  formatPercent,
  formatQuantity,
  isNegative,
} from "@/lib/decimal";
import type { Opportunity } from "@/lib/api/schema";

type Row = { term: string; value: string; note?: string };

/**
 * Every figure here is supplied by the backend. Nothing on this screen performs
 * arbitrage arithmetic; costs are listed separately so the reader can see what
 * the stated net profit is net of.
 */
export function CostBreakdown({
  opportunity,
  asset = "USD",
}: {
  opportunity: Opportunity;
  asset?: string;
}) {
  const costs: Row[] = [
    {
      term: "Executable depth cost",
      value:
        opportunity.estimated_outlay === null ||
        opportunity.estimated_outlay === undefined
          ? "not supplied"
          : formatMoney(opportunity.estimated_outlay, asset),
      note: "Cost of filling both legs against the quoted book depth.",
    },
    {
      term: "Fees",
      value: formatMoney(opportunity.fee_bound, asset),
      note: "Upper bound from the reviewed venue fee schedules.",
    },
    {
      term: "Slippage allowance",
      value: formatMoney(opportunity.slippage_reserve, asset),
      note: "Reserved for adverse movement between the two fills.",
    },
  ];

  const results: Row[] = [
    {
      term: "Capital required",
      value: formatMoney(opportunity.capital_required, asset),
      note: "Funds that must already be available on both venues.",
    },
    {
      term: "Minimum payout",
      value: formatMoney(opportunity.minimum_payout, asset),
      note: "The worst payout across every reviewed settlement outcome.",
    },
  ];

  const negative = isNegative(opportunity.net_profit);

  return (
    <div className="space-y-5">
      <div className="grid gap-5 sm:grid-cols-2">
        {[
          { heading: "Costs", rows: costs },
          { heading: "Requirements and payout", rows: results },
        ].map(({ heading, rows }) => (
          <div key={heading}>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              {heading}
            </h4>
            <dl className="mt-3 space-y-3.5">
              {rows.map((row) => (
                <div key={row.term}>
                  <div className="flex items-baseline justify-between gap-4">
                    <dt className="text-sm">{row.term}</dt>
                    <dd className="text-sm font-semibold tabular-nums">
                      {row.value}
                    </dd>
                  </div>
                  {row.note && (
                    <p className="mt-0.5 text-xs leading-5 text-muted-foreground">
                      {row.note}
                    </p>
                  )}
                </div>
              ))}
            </dl>
          </div>
        ))}
      </div>

      <div
        className={`rounded-lg border p-4 ${
          negative
            ? "border-red-300 bg-red-50"
            : "border-emerald-300 bg-emerald-50"
        }`}
      >
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <span className="text-sm font-semibold">
            Net {negative ? "loss" : "profit"} after all costs
          </span>
          <span className="text-2xl font-semibold tabular-nums">
            {formatMoney(opportunity.net_profit, asset)}
          </span>
        </div>
        <p className="mt-1.5 text-sm text-muted-foreground">
          {formatPercent(opportunity.return_on_capital)} on{" "}
          {formatMoney(opportunity.capital_required, asset)} of capital, for{" "}
          {formatQuantity(opportunity.quantity)} contracts on each leg.
        </p>
      </div>
    </div>
  );
}
