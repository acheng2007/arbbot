"use client";
import { useOpportunityStream } from "@/features/opportunities/use-stream";
import { StreamStatusBanner } from "@/features/opportunities/stream-status";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";
import { Search, SlidersHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/states";
import { OriginBanner } from "@/components/data-origin";
import { useApi } from "@/lib/query/hooks";
import { QueryState } from "@/features/shared/query-state";
import { PairedPrediction, PredictionCard } from "./prediction-card";
import {
  PAGE_SIZE,
  parseFilters,
  serializeFilters,
  type MarketFilters,
} from "./filters";
const CONTROL =
  "h-10 rounded-lg border border-border bg-card px-3 text-sm focus-visible:outline-2 focus-visible:outline-ring";
export function MarketBrowser() {
  const stream = useOpportunityStream();
  const router = useRouter();
  const params = useSearchParams();
  const filters = useMemo(
    () => parseFilters(new URLSearchParams(params.toString())),
    [params],
  );
  const [expanded, setExpanded] = useState(false);
  const paired = filters.view === "paired";
  const update = (changes: Partial<MarketFilters>) =>
    router.replace(
      `/markets${serializeFilters({ ...filters, ...changes, offset: "offset" in changes ? changes.offset! : 0 })}`,
      { scroll: false },
    );
  const common = {
    limit: PAGE_SIZE,
    offset: filters.offset,
    ...(filters.venue ? { venue: filters.venue } : {}),
    ...(filters.search.trim() ? { q: filters.search.trim() } : {}),
  };
  const markets = useApi(
    "marketSummaries",
    {
      query: {
        ...common,
        ...(filters.status ? { status: filters.status } : {}),
        ...(filters.category ? { category: filters.category } : {}),
      },
    },
    { enabled: !paired },
  );
  const matches = useApi(
    "matches",
    {
      query: {
        ...common,
        same_event: true,
        exclude_rejected: true,
        ...(filters.status ? { market_status: filters.status } : {}),
        ...(filters.category ? { category: filters.category } : {}),
      },
    },
    { enabled: paired },
  );
  const venues = useApi("venues");
  const query = paired ? matches : markets;
  const count = query.data?.data.length ?? 0;
  const narrowed = Boolean(
    filters.venue || filters.status || filters.category || filters.search,
  );
  return (
    <div className="space-y-4">
      <div
        className="flex gap-6 border-b border-border"
        aria-label="Market views"
      >
        {[
          ["paired", "Paired markets"],
          ["all", "All markets"],
        ].map(([view, label]) => (
          <button
            key={view}
            type="button"
            aria-pressed={filters.view === view}
            onClick={() => update({ view: view as MarketFilters["view"] })}
            className={`border-b-2 pb-3 text-sm font-semibold ${filters.view === view ? "border-primary text-foreground" : "border-transparent text-muted-foreground"}`}
          >
            {label}
          </button>
        ))}
      </div>
      <form
        role="search"
        aria-label="Filter markets"
        className="flex flex-wrap gap-2"
        onSubmit={(e) => e.preventDefault()}
      >
        <div className="relative w-full sm:min-w-64 sm:flex-1">
          <Search
            aria-hidden="true"
            className="absolute left-3 top-3 size-4 text-muted-foreground"
          />
          <label htmlFor="market-search" className="sr-only">
            Search all markets
          </label>
          <input
            id="market-search"
            type="search"
            value={filters.search}
            maxLength={200}
            placeholder="Search markets"
            onChange={(e) => update({ search: e.target.value })}
            className={`${CONTROL} w-full pl-9`}
          />
        </div>
        <label className="sr-only" htmlFor="market-venue">
          Venue
        </label>
        <select
          id="market-venue"
          value={filters.venue}
          onChange={(e) =>
            update({ venue: e.target.value as MarketFilters["venue"] })
          }
          className={`${CONTROL} min-w-0 flex-1 sm:flex-none`}
        >
          <option value="">All venues</option>
          {venues.data?.data
            .filter((v) => v.enabled)
            .map((v) => (
              <option key={v.id} value={v.id}>
                {v.name}
              </option>
            ))}
        </select>
        <Button
          type="button"
          variant="outline"
          aria-expanded={expanded}
          aria-controls="market-extra-filters"
          onClick={() => setExpanded(!expanded)}
        >
          <SlidersHorizontal aria-hidden="true" className="size-4" />
          Filters
        </Button>
        {(expanded || filters.status || filters.category) && (
          <div
            id="market-extra-filters"
            className="flex w-full flex-wrap items-center gap-2 rounded-lg bg-muted p-3"
          >
            <label htmlFor="market-status" className="text-xs">
              Status
            </label>
            <select
              id="market-status"
              value={filters.status}
              onChange={(e) =>
                update({ status: e.target.value as MarketFilters["status"] })
              }
              className={CONTROL}
            >
              <option value="">Any status</option>
              <option value="open">Open</option>
              <option value="closed">Closed</option>
            </select>
            <label htmlFor="market-category" className="text-xs">
              Category
            </label>
            <input
              id="market-category"
              value={filters.category}
              placeholder="Exact category"
              maxLength={100}
              onChange={(e) => update({ category: e.target.value })}
              className={`${CONTROL} min-w-0`}
            />
          </div>
        )}
        {narrowed && (
          <Button
            variant="outline"
            type="button"
            onClick={() =>
              update({ venue: "", status: "", category: "", search: "" })
            }
          >
            Clear filters
          </Button>
        )}
      </form>
      {query.data && <OriginBanner origin={query.data.origin} />}
      <StreamStatusBanner state={stream} />
      <QueryState
        isPending={query.isPending}
        error={query.error}
        loadingLabel="Loading markets"
        onRetry={() => void query.refetch()}
      >
        {count === 0 ? (
          <EmptyState
            title={paired ? "No paired markets found" : "No markets found"}
            description="Try broader filters or browse All markets."
          />
        ) : (
          <ul className="grid items-start gap-4 md:grid-cols-2">
            {paired
              ? matches.data?.data.map((match) => (
                  <li key={match.id}>
                    <PairedPrediction match={match} />
                  </li>
                ))
              : markets.data?.data.map((market) => (
                  <li key={market.id}>
                    <PredictionCard market={market} pairingState="ready" />
                  </li>
                ))}
          </ul>
        )}
      </QueryState>
      <nav
        aria-label="Market pages"
        className="flex items-center justify-between gap-3 border-t border-border pt-4"
      >
        <span className="text-xs text-muted-foreground">
          Page {Math.floor(filters.offset / PAGE_SIZE) + 1}
        </span>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={filters.offset === 0}
            onClick={() =>
              update({ offset: Math.max(0, filters.offset - PAGE_SIZE) })
            }
          >
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={query.isPending || count < PAGE_SIZE}
            onClick={() => update({ offset: filters.offset + PAGE_SIZE })}
          >
            Next
          </Button>
        </div>
      </nav>
    </div>
  );
}
