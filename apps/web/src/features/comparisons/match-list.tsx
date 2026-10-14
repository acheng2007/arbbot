"use client";
import { ModeBadge } from "@/components/data-origin";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { EmptyState } from "@/components/states";
import { OriginBanner } from "@/components/data-origin";
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
  const [offset, setOffset] = useState(0);
  const [classification, setClassification] = useState<
    "suggested" | "pending" | "stale" | "unavailable" | ""
  >("");
  const [search, setSearch] = useState("");
  const matches = useApi("matches", {
    query: {
      limit: 25,
      offset,
      ...(classification ? { classification } : {}),
      ...(search.trim() ? { q: search.trim() } : {}),
    },
  });
  const { index } = useMarketIndex(
    matches.data?.data.flatMap((match) => [match.left_id, match.right_id]) ??
      [],
  );

  return (
    <div className="space-y-6">
      {matches.data && <OriginBanner origin={matches.data.origin} />}
      <div className="grid gap-3 sm:grid-cols-[1fr_240px]">
        <label className="block text-sm font-medium">
          Search comparisons
          <input
            type="search"
            value={search}
            maxLength={200}
            onChange={(event) => {
              setSearch(event.target.value);
              setOffset(0);
            }}
            className="mt-2 block h-11 w-full rounded-md border border-border bg-card px-3"
          />
        </label>
        <label className="block text-sm font-medium">
          AI classification filter
          <select
            value={classification}
            onChange={(event) => {
              setClassification(event.target.value as typeof classification);
              setOffset(0);
            }}
            className="mt-2 block h-11 w-full rounded-md border border-border bg-card px-3"
          >
            <option value="">All classifications</option>
            <option value="suggested">AI suggests same event</option>
            <option value="pending">Pending</option>
            <option value="stale">Stale</option>
            <option value="unavailable">Unavailable</option>
          </select>
        </label>
      </div>
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
                      <ModeBadge
                        mode={match.mode}
                        feedOrigin={match.feed_origin}
                      />
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
                    <p className="mt-3 text-xs text-muted-foreground">
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
      <nav
        aria-label="Comparison pages"
        className="flex items-center justify-between gap-3"
      >
        <span className="text-sm">Page {Math.floor(offset / 25) + 1}</span>
        <div className="flex gap-2">
          <Button
            variant="outline"
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - 25))}
          >
            Previous
          </Button>
          <Button
            variant="outline"
            disabled={(matches.data?.data.length ?? 0) < 25}
            onClick={() => setOffset(offset + 25)}
          >
            Next
          </Button>
        </div>
      </nav>
    </div>
  );
}
