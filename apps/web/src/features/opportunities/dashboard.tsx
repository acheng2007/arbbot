"use client";
import Link from "next/link";
import { EmptyState } from "@/components/states";
import { OriginBanner } from "@/components/data-origin";
import { Timestamp } from "@/components/timestamp";
import { Badge } from "@/components/ui/badge";
import { formatMoney, formatQuantity } from "@/lib/decimal";
import { useApi } from "@/lib/query/hooks";
import { QueryState } from "@/features/shared/query-state";
import { useMarketIndex } from "@/features/shared/use-market-index";
import { OpportunityCard } from "./opportunity-card";
import { StreamStatusBanner } from "./stream-status";
import { useOpportunityStream } from "./use-stream";

function BlockedEvaluations() {
  const evaluations = useApi("evaluations", { query: { limit: 50 } });
  const matches = useApi("matches", { query: { limit: 200 } });
  const { index } = useMarketIndex();
  const blocked = (evaluations.data?.data ?? []).filter(
    (evaluation) => evaluation.blocked_reasons.length > 0,
  );
  if (blocked.length === 0) return null;

  const describe = (matchId: string) => {
    const match = matches.data?.data.find((entry) => entry.id === matchId);
    if (!match) return matchId;
    const left = index.get(match.left_id)?.title;
    const right = index.get(match.right_id)?.title;
    return left && right ? `${left} against ${right}` : matchId;
  };

  return (
    <section aria-labelledby="blocked-heading">
      <h2 id="blocked-heading" className="text-lg font-semibold">
        Evaluated but not tradable
      </h2>
      <p className="mt-1.5 mb-4 text-sm leading-6 text-muted-foreground">
        These pairs were evaluated and produced no opportunity. The reasons are
        recorded rather than hidden.
      </p>
      <ul className="space-y-3">
        {blocked.map((evaluation) => (
          <li
            key={evaluation.match_id}
            className="rounded-lg border border-border bg-card p-4 sm:p-5"
          >
            <Link
              href={`/matches/${encodeURIComponent(evaluation.match_id)}`}
              className="text-sm font-medium text-primary"
            >
              {describe(evaluation.match_id)}
            </Link>
            <ul className="mt-2.5 list-disc space-y-1 pl-5 text-sm leading-6 text-muted-foreground">
              {evaluation.blocked_reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function OpportunityDashboard() {
  const opportunities = useApi("opportunities", { query: { limit: 100 } });
  const { index } = useMarketIndex();
  const stream = useOpportunityStream();

  return (
    <div className="space-y-7">
      {opportunities.data && (
        <OriginBanner origin={opportunities.data.origin} />
      )}
      <StreamStatusBanner state={stream} />

      <p className="rounded-lg border border-border bg-card p-4 text-sm leading-6">
        Figures below are calculated by the backend from executable quotes and
        reviewed fee schedules. They are conditional estimates, not guaranteed
        profit: the two legs settle on separate venues, fills are not atomic,
        and quotes can move or disappear before an order reaches either book.
      </p>

      <QueryState
        isPending={opportunities.isPending}
        error={opportunities.error}
        loadingLabel="Loading opportunities"
        onRetry={() => void opportunities.refetch()}
      >
        {opportunities.data?.data.length === 0 ? (
          <EmptyState
            title="No opportunities right now"
            description="No verified pair currently shows a positive net result after fees, depth costs, and the slippage allowance. This is the normal state most of the time."
          />
        ) : (
          <ul className="space-y-5">
            {opportunities.data?.data.map((opportunity) => (
              <li key={opportunity.id}>
                <OpportunityCard opportunity={opportunity} markets={index} />
              </li>
            ))}
          </ul>
        )}
      </QueryState>

      <BlockedEvaluations />
      <RecentHistory />
    </div>
  );
}

function RecentHistory() {
  const history = useApi("history", { query: { limit: 20 } });
  const entries = history.data?.data ?? [];
  if (entries.length === 0) return null;

  return (
    <section aria-labelledby="history-heading">
      <h2 id="history-heading" className="text-lg font-semibold">
        Recently expired
      </h2>
      <p className="mt-1.5 mb-4 text-sm leading-6 text-muted-foreground">
        Previous evaluations kept for audit. These quotes have expired and are
        not actionable.
      </p>
      <ul className="space-y-3">
        {entries.map((entry) => (
          <li
            key={entry.id}
            className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-card p-4"
          >
            <Badge tone="neutral">Expired</Badge>
            <Link
              href={`/opportunities/${encodeURIComponent(entry.id)}`}
              className="text-sm font-medium text-primary"
            >
              {formatMoney(entry.net_profit)} estimated on{" "}
              {formatQuantity(entry.quantity)} contracts
            </Link>
            <span className="text-sm text-muted-foreground">
              evaluated <Timestamp value={entry.evaluated_at} />
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
