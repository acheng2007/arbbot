"use client";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { EmptyState } from "@/components/states";
import { OriginBanner } from "@/components/data-origin";
import { Badge } from "@/components/ui/badge";
import { useApi } from "@/lib/query/hooks";
import type { Match } from "@/lib/api/schema";
import { QueryState } from "@/features/shared/query-state";
import { useMarketIndex } from "@/features/shared/use-market-index";
import {
  ComparisonStatusBadge,
  MatchStatusBadge,
  venueLabel,
} from "@/features/shared/status";

function unresolvedCount(match: Match) {
  return (match.comparison?.differences ?? []).filter(
    (difference) => difference.status !== "equal",
  ).length;
}

export function MatchList() {
  const matches = useApi("matches", { query: { limit: 100 } });
  const { index } = useMarketIndex();

  return (
    <div className="space-y-6">
      {matches.data && <OriginBanner origin={matches.data.origin} />}
      <QueryState
        isPending={matches.isPending}
        error={matches.error}
        loadingLabel="Loading proposed pairs"
        onRetry={() => void matches.refetch()}
      >
        {matches.data?.data.length === 0 ? (
          <EmptyState
            title="No proposed pairs yet"
            description="Contract pairs appear here once discovery finds candidates across two venues. A pair is only ever shown as verified after a recorded review of its settlement terms."
          />
        ) : (
          <ul className="space-y-4">
            {matches.data?.data.map((match) => {
              const left = index.get(match.left_id);
              const right = index.get(match.right_id);
              const unresolved = unresolvedCount(match);
              return (
                <li key={match.id}>
                  <Link
                    href={`/matches/${encodeURIComponent(match.id)}`}
                    className="block rounded-xl border border-border bg-card p-5 transition-colors hover:border-ring focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring sm:p-6"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <MatchStatusBadge status={match.status} />
                      {match.comparison && (
                        <ComparisonStatusBadge
                          status={match.comparison.status}
                        />
                      )}
                      <Badge
                        tone={match.mode === "live" ? "positive" : "caution"}
                      >
                        {match.mode === "live" ? "Live feed" : "Simulation"}
                      </Badge>
                      <span className="ml-auto hidden text-sm font-medium text-primary sm:flex sm:items-center sm:gap-1">
                        Inspect terms
                        <ArrowRight aria-hidden="true" className="size-4" />
                      </span>
                    </div>
                    <div className="mt-4 grid gap-4 md:grid-cols-2">
                      {[
                        { market: left, id: match.left_id },
                        { market: right, id: match.right_id },
                      ].map(({ market, id }) => (
                        <div key={id} className="min-w-0">
                          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                            {market
                              ? venueLabel(market.venue)
                              : "Unknown venue"}
                          </p>
                          <p className="mt-1.5 font-medium leading-6">
                            {market?.title ?? id}
                          </p>
                        </div>
                      ))}
                    </div>
                    <p className="mt-4 text-sm leading-6 text-muted-foreground">
                      {match.reason}
                    </p>
                    <p className="mt-3 text-xs text-muted-foreground">
                      Title similarity {match.similarity.toFixed(2)}, a
                      discovery signal only.{" "}
                      {unresolved > 0
                        ? `${unresolved} settlement ${unresolved === 1 ? "field" : "fields"} still differ or are unknown.`
                        : "All compared settlement fields agree."}
                    </p>
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </QueryState>
    </div>
  );
}
