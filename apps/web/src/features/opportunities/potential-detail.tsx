"use client";
import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { OriginBanner } from "@/components/data-origin";
import { QueryState } from "@/features/shared/query-state";
import { useMarketIndex } from "@/features/shared/use-market-index";
import { useApi } from "@/lib/query/hooks";
import { useOpportunityStream } from "./use-stream";
import { StreamStatusBanner } from "./stream-status";
import { PotentialCard } from "./potential-card";

export function PotentialDetail({ id }: { id: string }) {
  const [historical, setHistorical] = useState(false);
  const result = useApi("potentialOpportunity", {
    params: { potential_id: id },
    query: { historical },
  });
  const { index } = useMarketIndex(result.data?.data.market_ids ?? []);
  const stream = useOpportunityStream();
  return (
    <div className="space-y-5">
      <Link
        href="/opportunities?view=potential"
        className="text-sm font-medium text-primary"
      >
        All potential price gaps
      </Link>
      <StreamStatusBanner state={stream} />
      <h1 className="text-2xl font-semibold">
        {historical ? "Recorded potential price gap" : "Potential price gap"}
      </h1>
      <p className="text-sm leading-6 text-muted-foreground">
        An ordinary-outcome discrepancy does not establish settlement
        compatibility or qualified profit.
      </p>
      {result.data && <OriginBanner origin={result.data.origin} />}
      {result.error?.failure === "not_found" && !historical ? (
        <section className="rounded-xl border border-border p-5">
          <p className="mb-3 text-sm leading-6">
            This gap is no longer current. Quotes, terms, fees, or assessment
            inputs may have changed.
          </p>
          <Button variant="outline" onClick={() => setHistorical(true)}>
            Inspect historical result
          </Button>
        </section>
      ) : (
        <QueryState
          isPending={result.isPending}
          error={result.error}
          loadingLabel="Loading price gap"
          onRetry={() => void result.refetch()}
        >
          {result.data && (
            <>
              {historical && (
                <p
                  role="status"
                  className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950"
                >
                  Historical inputs only. This result is not current or
                  actionable.
                </p>
              )}
              <PotentialCard item={result.data.data} markets={index} detail />
            </>
          )}
        </QueryState>
      )}
    </div>
  );
}
