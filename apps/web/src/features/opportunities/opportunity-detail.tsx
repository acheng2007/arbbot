"use client";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/states";
import { OriginBanner } from "@/components/data-origin";
import { Timestamp } from "@/components/timestamp";
import { ValidUntil } from "@/components/freshness";
import { formatMoney } from "@/lib/decimal";
import type { Opportunity } from "@/lib/api/schema";
import { useApi } from "@/lib/query/hooks";
import { QueryState } from "@/features/shared/query-state";
import { useMarketIndex } from "@/features/shared/use-market-index";
import { venueLabel } from "@/features/shared/status";
import { ReviewPanel } from "@/features/comparisons/review-panel";
import { DifferenceTable } from "@/features/comparisons/difference-table";
import { CostBreakdown } from "./cost-breakdown";
import { ClassificationBadge, LegSummary } from "./opportunity-card";

function ScenarioPayouts({
  opportunity,
  asset,
}: {
  opportunity: Opportunity;
  asset: string;
}) {
  const entries = Object.entries(opportunity.scenario_payouts);
  if (entries.length === 0) return null;
  return (
    <section className="rounded-xl border border-border bg-card p-5 sm:p-6">
      <h2 className="text-lg font-semibold">
        Payout in every settlement outcome
      </h2>
      <p className="mt-1.5 text-sm leading-6 text-muted-foreground">
        The combined position is checked against each reviewed outcome. A
        positive result in only some outcomes is not arbitrage.
      </p>
      <table className="mt-4 w-full text-sm">
        <caption className="sr-only">Net result by settlement outcome</caption>
        <thead>
          <tr className="border-b border-border text-left text-muted-foreground">
            <th scope="col" className="py-2 font-medium">
              Outcome
            </th>
            <th scope="col" className="py-2 text-right font-medium">
              Net result
            </th>
          </tr>
        </thead>
        <tbody>
          {entries.map(([name, payout]) => (
            <tr key={name} className="border-b border-border/60">
              <td className="py-2.5 pr-4">{name}</td>
              <td className="py-2.5 text-right tabular-nums">
                {payout === undefined
                  ? "not supplied"
                  : formatMoney(payout, asset)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

export function OpportunityDetail({
  opportunityId,
}: {
  opportunityId: string;
}) {
  const current = useApi("opportunities", { query: { limit: 200 } });
  const history = useApi("history", { query: { limit: 200 } });
  const { index } = useMarketIndex();

  const live = current.data?.data.find((entry) => entry.id === opportunityId);
  const archived = history.data?.data.find(
    (entry) => entry.id === opportunityId,
  );
  const opportunity = live ?? archived;

  return (
    <div className="space-y-7">
      <Link
        href="/opportunities"
        className="inline-flex items-center gap-1.5 text-sm font-medium text-primary"
      >
        <ArrowLeft aria-hidden="true" className="size-4" />
        All opportunities
      </Link>

      {current.data && <OriginBanner origin={current.data.origin} />}

      <QueryState
        isPending={current.isPending || history.isPending}
        error={current.error}
        loadingLabel="Loading opportunity"
        onRetry={() => void current.refetch()}
      >
        {!opportunity ? (
          <EmptyState
            title="This opportunity is no longer available"
            description="Opportunities expire as soon as the quotes behind them do. It may have been superseded by a newer evaluation, or the identifier may be wrong."
          />
        ) : (
          (() => {
            const asset =
              index.get(opportunity.legs[0].market_id)?.settlement_asset ??
              "USD";
            const legVenue = (position: 0 | 1) => {
              const market = index.get(opportunity.legs[position].market_id);
              return market
                ? venueLabel(market.venue)
                : opportunity.legs[position].market_id;
            };
            return (
              <div className="space-y-7">
                <header className="space-y-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <ClassificationBadge
                      classification={opportunity.classification}
                    />
                    <Badge
                      tone={
                        opportunity.mode === "live" ? "positive" : "caution"
                      }
                    >
                      {opportunity.mode === "live" ? "Live feed" : "Simulation"}
                    </Badge>
                    <ValidUntil validUntil={opportunity.valid_until} />
                    {!live && <Badge tone="neutral">From history</Badge>}
                  </div>
                  <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
                    {formatMoney(opportunity.net_profit, asset)} estimated net
                    profit
                  </h1>
                  <p className="max-w-3xl text-base leading-7 text-muted-foreground">
                    Evaluated <Timestamp value={opportunity.evaluated_at} />{" "}
                    from the quotes below. This is a conditional estimate on
                    non-atomic, cross-venue fills, not a guaranteed result.
                  </p>
                  <Link
                    href={`/matches/${encodeURIComponent(opportunity.match_id)}`}
                    className="inline-block text-sm font-medium text-primary"
                  >
                    Inspect the contract comparison behind this pair
                  </Link>
                </header>

                <section className="rounded-xl border border-border bg-card p-5 sm:p-6">
                  <h2 className="text-lg font-semibold">Cost and result</h2>
                  <div className="mt-4">
                    <CostBreakdown opportunity={opportunity} asset={asset} />
                  </div>
                </section>

                <section>
                  <h2 className="text-lg font-semibold">Legs and quotes</h2>
                  <div className="mt-4 grid gap-4 md:grid-cols-2">
                    {opportunity.legs.map((leg) => (
                      <LegSummary
                        key={`${leg.market_id}-${leg.outcome}`}
                        leg={leg}
                        market={index.get(leg.market_id)}
                      />
                    ))}
                  </div>
                </section>

                <ScenarioPayouts opportunity={opportunity} asset={asset} />

                <section className="rounded-xl border border-amber-300 bg-amber-50 p-5 sm:p-6">
                  <h2 className="font-semibold text-amber-950">
                    Execution assumptions
                  </h2>
                  <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-6 text-amber-950">
                    {opportunity.assumptions.map((assumption) => (
                      <li key={assumption}>{assumption}</li>
                    ))}
                    <li>
                      No order is placed by this system. Discovery and
                      evaluation only.
                    </li>
                  </ul>
                </section>

                <ReviewPanel
                  review={opportunity.review}
                  left={index.get(opportunity.review.left_id)}
                  right={index.get(opportunity.review.right_id)}
                />

                {opportunity.comparison && (
                  <section>
                    <h2 className="text-lg font-semibold">
                      Settlement terms behind this pair
                    </h2>
                    <div className="mt-4">
                      <DifferenceTable
                        comparison={opportunity.comparison}
                        leftLabel={legVenue(0)}
                        rightLabel={legVenue(1)}
                      />
                    </div>
                  </section>
                )}
              </div>
            );
          })()
        )}
      </QueryState>
    </div>
  );
}
