import { Suspense } from "react";
import type { Metadata } from "next";
import { LoadingState } from "@/components/states";
import { MarketBrowser } from "@/features/markets/market-browser";

export const metadata: Metadata = {
  title: "Markets",
  description:
    "Browse discovered markets, inspect original terms, and check quote health per venue.",
};

export default function MarketsPage() {
  return (
    <div className="space-y-7">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
          Markets
        </h1>
        <p className="mt-3 max-w-2xl text-base leading-7 text-muted-foreground">
          One prediction, both exchanges. Compare Polymarket and Kalshi
          prices together, then inspect each contract’s depth and source terms.
        </p>
      </header>
      {/* useSearchParams needs a boundary so the shell can render before filters resolve. */}
      <Suspense fallback={<LoadingState label="Loading markets" />}>
        <MarketBrowser />
      </Suspense>
    </div>
  );
}
