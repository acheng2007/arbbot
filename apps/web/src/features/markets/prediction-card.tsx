"use client";
import Link from "next/link";
import type { Market, Match } from "@/lib/api/schema";
import { useApi } from "@/lib/query/hooks";
import { Badge } from "@/components/ui/badge";
import { venueLabel } from "@/features/shared/status";
import { MarketPrices } from "./market-prices";

function VenuePrices({ market }: { market: Market }) {
  return (
    <div className="min-w-0 rounded-lg border border-border bg-background p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-semibold">{venueLabel(market.venue)}</h3>
        <Badge tone={market.mode === "live" ? "positive" : "caution"}>
          {market.mode === "live" ? "Live feed" : "Simulation"}
        </Badge>
      </div>
      <Link
        className="mt-2 block text-sm leading-6 underline underline-offset-4"
        href={`/markets/${encodeURIComponent(market.id)}`}
      >
        {market.title}
      </Link>
      <p className="mt-2 text-xs text-muted-foreground">
        {market.status === "open" ? "Open" : "Closed"}
      </p>
      <MarketPrices marketId={market.id} />
    </div>
  );
}

export function PredictionCard({
  market,
  match,
  pairingState,
}: {
  market: Market;
  match?: Match;
  pairingState: "loading" | "error" | "ready";
}) {
  const counterpartId =
    match && (match.left_id === market.id ? match.right_id : match.left_id);
  const counterpart = useApi(
    "market",
    { params: { market_id: counterpartId ?? "" } },
    { enabled: Boolean(counterpartId) },
  );
  const other = counterpart.isError ? undefined : counterpart.data?.data;
  const contracts = [
    market,
    ...(other && other.venue !== market.venue && other.mode === market.mode
      ? [other]
      : []),
  ];
  return (
    <article
      className="rounded-xl border border-border bg-card p-4 sm:p-5"
      aria-label={market.title}
    >
      <h2 className="text-lg font-semibold leading-7">{market.title}</h2>
      {match && (
        <Link
          href={`/matches/${encodeURIComponent(match.id)}`}
          className="mt-2 inline-block text-xs text-muted-foreground underline underline-offset-4"
        >
          Same-event comparison · Inspect settlement review
        </Link>
      )}
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        {(["polymarket", "kalshi"] as const).map((venue) => {
          const contract = contracts.find((item) => item.venue === venue);
          return contract ? (
            <VenuePrices key={venue} market={contract} />
          ) : (
            <div
              key={venue}
              className="rounded-lg border border-dashed border-border p-4"
            >
              <h3 className="font-semibold">{venueLabel(venue)}</h3>
              <p className="mt-4 text-sm text-muted-foreground">
                {pairingState === "loading" ||
                (counterpartId && counterpart.isPending)
                  ? "Loading counterpart..."
                  : pairingState === "error" || counterpart.isError
                    ? "Comparison unavailable. Try refreshing the page."
                    : "No same-event counterpart available in loaded comparisons."}
              </p>
            </div>
          );
        })}
      </div>
    </article>
  );
}
