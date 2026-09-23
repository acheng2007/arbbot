"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo } from "react";
import { Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/states";
import { OriginBanner } from "@/components/data-origin";
import { Age } from "@/components/freshness";
import { useApi } from "@/lib/query/hooks";
import { QueryState } from "@/features/shared/query-state";
import { venueLabel } from "@/features/shared/status";
import {
  applyLocalFilters,
  PAGE_SIZE,
  parseFilters,
  serializeFilters,
  type MarketFilters,
} from "./filters";

const CONTROL =
  "h-11 rounded-md border border-border bg-card px-3 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring";

export function MarketBrowser() {
  const router = useRouter();
  const params = useSearchParams();
  const filters = useMemo(
    () => parseFilters(new URLSearchParams(params.toString())),
    [params],
  );

  const update = (changes: Partial<MarketFilters>) => {
    const next = { ...filters, ...changes };
    // Any filter change invalidates the current page position.
    if (!("offset" in changes)) next.offset = 0;
    router.replace(`/markets${serializeFilters(next)}`, { scroll: false });
  };

  const markets = useApi("markets", {
    query: {
      limit: PAGE_SIZE,
      offset: filters.offset,
      ...(filters.venue ? { venue: filters.venue } : {}),
    },
  });

  const loaded = markets.data?.data ?? [];
  const visible = applyLocalFilters(loaded, filters);
  const narrowed = Boolean(filters.status || filters.search.trim());
  const page = Math.floor(filters.offset / PAGE_SIZE) + 1;

  return (
    <div className="space-y-6">
      {markets.data && <OriginBanner origin={markets.data.origin} />}

      <form
        role="search"
        aria-label="Filter markets"
        className="flex flex-wrap items-end gap-3 rounded-xl border border-border bg-card p-4 sm:p-5"
        onSubmit={(event) => event.preventDefault()}
      >
        <div className="flex min-w-[14rem] flex-1 flex-col gap-1.5">
          <label htmlFor="market-search" className="text-xs font-semibold">
            Search the loaded page
          </label>
          <div className="relative">
            <Search
              aria-hidden="true"
              className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
            />
            <input
              id="market-search"
              type="search"
              value={filters.search}
              placeholder="Title or venue identifier"
              onChange={(event) => update({ search: event.target.value })}
              className={`${CONTROL} w-full pl-9`}
            />
          </div>
        </div>
        <div className="flex flex-col gap-1.5">
          <label htmlFor="market-venue" className="text-xs font-semibold">
            Venue
          </label>
          <select
            id="market-venue"
            value={filters.venue}
            onChange={(event) =>
              update({ venue: event.target.value as MarketFilters["venue"] })
            }
            className={CONTROL}
          >
            <option value="">All venues</option>
            <option value="kalshi">Kalshi</option>
            <option value="polymarket">Polymarket</option>
          </select>
        </div>
        <div className="flex flex-col gap-1.5">
          <label htmlFor="market-status" className="text-xs font-semibold">
            Status
          </label>
          <select
            id="market-status"
            value={filters.status}
            onChange={(event) =>
              update({ status: event.target.value as MarketFilters["status"] })
            }
            className={CONTROL}
          >
            <option value="">Any status</option>
            <option value="open">Open</option>
            <option value="closed">Closed</option>
          </select>
        </div>
        {(filters.venue || narrowed) && (
          <Button
            type="button"
            variant="outline"
            onClick={() => router.replace("/markets", { scroll: false })}
          >
            Clear filters
          </Button>
        )}
      </form>

      <p className="text-sm leading-6 text-muted-foreground">
        Venue and page position are applied by the API. Status and text search
        narrow the {loaded.length} markets on this page only, because
        catalog-wide filtering is not yet available from the backend.
      </p>

      <QueryState
        isPending={markets.isPending}
        error={markets.error}
        loadingLabel="Loading markets"
        onRetry={() => void markets.refetch()}
      >
        {visible.length === 0 ? (
          <EmptyState
            title={
              narrowed
                ? "No markets match these filters"
                : "No markets on this page"
            }
            description={
              narrowed
                ? "Try a broader search, or clear the filters to see everything the API returned for this page."
                : "The API returned no markets for this venue and page. Ingestion may not have discovered any yet."
            }
          />
        ) : (
          <ul className="space-y-3">
            {visible.map((market) => (
              <li key={market.id}>
                <Link
                  href={`/markets/${encodeURIComponent(market.id)}`}
                  className="block rounded-xl border border-border bg-card p-5 transition-colors hover:border-ring focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone="neutral">{venueLabel(market.venue)}</Badge>
                    <Badge
                      tone={market.status === "open" ? "positive" : "neutral"}
                    >
                      {market.status === "open" ? "Open" : "Closed"}
                    </Badge>
                    <Badge
                      tone={market.mode === "live" ? "positive" : "caution"}
                    >
                      {market.mode === "live" ? "Live feed" : "Simulation"}
                    </Badge>
                    <Age at={market.observed_at} label="Observed" />
                  </div>
                  <p className="mt-3 font-medium leading-6">{market.title}</p>
                  <p className="mt-2 font-mono text-xs break-all text-muted-foreground">
                    {market.external_id}
                  </p>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </QueryState>

      <nav
        aria-label="Market pages"
        className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-5"
      >
        <span className="text-sm text-muted-foreground">
          Page {page}, showing {visible.length} of {loaded.length} loaded
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
            disabled={loaded.length < PAGE_SIZE}
            onClick={() => update({ offset: filters.offset + PAGE_SIZE })}
          >
            Next
          </Button>
        </div>
      </nav>
    </div>
  );
}
