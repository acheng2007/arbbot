"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo } from "react";
import { Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/states";
import { OriginBanner } from "@/components/data-origin";
import { useApi } from "@/lib/query/hooks";
import { QueryState } from "@/features/shared/query-state";
import { PairedPrediction, PredictionCard } from "./prediction-card";
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

  const venues = useApi("venues");
  const matches = useApi("matches", { query: { limit: 200 } });
  const pairedIds = new Set<string>();
  const pairs = (matches.isError ? [] : (matches.data?.data ?? [])).filter(
    (match) => {
      if (
        match.status === "rejected" ||
        match.comparison?.same_event !== true ||
        pairedIds.has(match.left_id) ||
        pairedIds.has(match.right_id)
      )
        return false;
      pairedIds.add(match.left_id);
      pairedIds.add(match.right_id);
      return true;
    },
  );

  const loaded = markets.data?.data ?? [];
  const visible = applyLocalFilters(loaded, filters);
  const cards = visible.filter(
    (market, index) =>
      !pairs.some(
        (pair) =>
          (pair.left_id === market.id || pair.right_id === market.id) &&
          visible
            .slice(0, index)
            .some(
              (earlier) =>
                earlier.id === pair.left_id || earlier.id === pair.right_id,
            ),
      ),
  );
  const narrowed = Boolean(filters.status || filters.search.trim());
  const showFeatured = !filters.venue && !narrowed && filters.offset === 0;
  const page = Math.floor(filters.offset / PAGE_SIZE) + 1;

  return (
    <div className="space-y-6">
      {markets.data && <OriginBanner origin={markets.data.origin} />}

      {showFeatured && pairs.length > 0 && (
        <section aria-label="Cross-exchange predictions" className="space-y-3">
          <h2 className="text-xl font-semibold">Cross-exchange predictions</h2>
          <p className="text-sm text-muted-foreground">
            Same-event candidates from both venues. Check settlement differences
            before comparing prices.
          </p>
          {pairs.map((match) => (
            <PairedPrediction key={match.id} match={match} />
          ))}
        </section>
      )}

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
            {venues.data?.data.filter((v) => v.enabled).map((v) => (
              <option key={v.id} value={v.id}>{v.name}</option>
            ))}
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
        Best asks refresh every 5 seconds while this page is visible, before
        fees. Predictions with a recorded same-event comparison show both venues
        together. Pairing uses the first 200 comparison records; unpaired
        contracts remain visible. Open a market to inspect depth and source
        terms. Venue and page position are applied by the API. Status and text
        search narrow the {loaded.length} markets on this page only, because
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
            {cards
              .filter((market) => !showFeatured || !pairedIds.has(market.id))
              .map((market) => (
                <li key={market.id}>
                  <PredictionCard
                    market={market}
                    match={pairs.find(
                      (pair) =>
                        pair.left_id === market.id ||
                        pair.right_id === market.id,
                    )}
                    pairingState={
                      matches.isPending
                        ? "loading"
                        : matches.isError
                          ? "error"
                          : "ready"
                    }
                  />
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
          Page {page}, {cards.length} predictions from {visible.length} of{" "}
          {loaded.length} loaded contracts
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
