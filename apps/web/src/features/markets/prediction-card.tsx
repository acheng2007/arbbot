"use client";
import { ModeBadge } from "@/components/data-origin";
import Link from "next/link";
import type { Market, MarketSummary, Match } from "@/lib/api/schema";
import { useApi } from "@/lib/query/hooks";
import { MatchStatusBadge, venueLabel } from "@/features/shared/status";
import { MarketPrices } from "./market-prices";
export function PairedPrediction({ match }: { match: Match }) {
  const market = useApi("market", { params: { market_id: match.left_id } });
  if (market.isPending)
    return (
      <div
        role="status"
        className="rounded-xl border border-border bg-card p-5"
      >
        Loading paired prediction...
      </div>
    );
  if (!market.data)
    return (
      <div role="alert" className="rounded-xl border border-border p-5">
        Paired prediction unavailable.{" "}
        <button onClick={() => void market.refetch()} className="underline">
          Retry
        </button>
      </div>
    );
  return (
    <PredictionCard
      market={market.data.data}
      match={match}
      pairingState="ready"
    />
  );
}
function VenuePrices({
  market,
  showOrigin = false,
}: {
  market: Market | MarketSummary;
  showOrigin?: boolean;
}) {
  return (
    <div className="border-t border-border py-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <Link
          href={`/markets/${encodeURIComponent(market.id)}`}
          className="text-sm font-semibold hover:text-primary"
        >
          {venueLabel(market.venue)}
        </Link>
        <span className="text-xs text-muted-foreground">
          {market.status === "closed" ? "Closed" : ""}
        </span>
      </div>
      {showOrigin && (
        <div className="mb-2">
          <ModeBadge mode={market.mode} feedOrigin={market.feed_origin} />
        </div>
      )}
      {!!market.ingestion_issues?.length && (
        <p role="alert" className="mb-2 text-xs text-amber-800">
          Unsupported instrument data · Estimates blocked
        </p>
      )}
      <MarketPrices
        marketId={market.id}
        shortNo={market.venue === "polymarket_us"}
      />
    </div>
  );
}
export function PredictionCard({
  market,
  match,
}: {
  market: Market | MarketSummary;
  match?: Match;
  pairingState: "loading" | "error" | "ready";
}) {
  const otherId = match
    ? match.left_id === market.id
      ? match.right_id
      : match.left_id
    : "";
  const counterpart = useApi(
    "market",
    { params: { market_id: otherId } },
    { enabled: Boolean(otherId) },
  );
  const other = counterpart.data?.data;
  return (
    <article
      aria-label={market.title}
      className="rounded-xl border border-border bg-card p-4 transition-colors hover:border-primary/40 sm:p-5"
    >
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <ModeBadge mode={market.mode} feedOrigin={market.feed_origin} />
        {match && <MatchStatusBadge status={match.status} />}
      </div>
      <h2 className="mb-4 text-lg font-semibold leading-6 tracking-tight">
        <Link
          href={
            match
              ? `/matches/${encodeURIComponent(match.id)}`
              : `/markets/${encodeURIComponent(market.id)}`
          }
          className="hover:text-primary"
        >
          {market.title}
        </Link>
      </h2>
      <VenuePrices market={market} />
      {other && other.venue !== market.venue && other.mode === market.mode ? (
        <VenuePrices
          market={other}
          showOrigin={
            (other.feed_origin ?? "exchange") !==
            (market.feed_origin ?? "exchange")
          }
        />
      ) : match ? (
        <p
          role="status"
          className="border-t border-border py-3 text-xs text-muted-foreground"
        >
          {counterpart.isPending
            ? "Loading counterpart..."
            : "Counterpart unavailable"}
        </p>
      ) : (
        <p className="border-t border-border py-3 text-xs text-muted-foreground">
          Open market to browse counterparts.
        </p>
      )}
      {match && (
        <Link
          href={`/matches/${encodeURIComponent(match.id)}`}
          className="inline-block pt-2 text-xs font-medium text-primary"
        >
          {match.status === "verified"
            ? "View comparison"
            : "Settlement review required"}{" "}
          →
        </Link>
      )}
    </article>
  );
}
