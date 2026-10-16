import { Suspense } from "react";
import type { Metadata } from "next";
import { LoadingState } from "@/components/states";
import { MarketBrowser } from "@/features/markets/market-browser";

export const metadata: Metadata = {
  title: "Discoveries",
  description:
    "Browse discovered markets, inspect original terms, and check quote health per venue.",
};

export default function MarketsPage() {
  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
          Discoveries
        </h1>
      </header>
      {/* useSearchParams needs a boundary so the shell can render before filters resolve. */}
      <Suspense fallback={<LoadingState label="Loading markets" />}>
        <MarketBrowser />
      </Suspense>
    </div>
  );
}
