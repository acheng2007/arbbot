"use client";
import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/states";
import { useApi } from "@/lib/query/hooks";
import { useMarketIndex } from "@/features/shared/use-market-index";
import { QueryState } from "@/features/shared/query-state";
import { MatchStatusBadge } from "@/features/shared/status";

const PAGE_SIZE = 20;

export function Counterparts({ marketId }: { marketId: string }) {
  const [offset, setOffset] = useState(0);
  const matches = useApi("matches", {
    query: { market_id: marketId, limit: PAGE_SIZE, offset },
  });
  const rows = matches.data?.data ?? [];
  const { index } = useMarketIndex(
    rows.map((row) => (row.left_id === marketId ? row.right_id : row.left_id)),
  );
  return (
    <section aria-label="Proposed counterparts" className="space-y-4">
      <h2 className="text-lg font-semibold">Proposed counterparts</h2>
      <p className="text-sm text-muted-foreground">
        Suggestions require automatic settlement checks. Every proposed pair can
        be inspected independently.
      </p>
      <QueryState
        isPending={matches.isPending}
        error={matches.error}
        loadingLabel="Loading counterparts"
        onRetry={() => void matches.refetch()}
      >
        {rows.length === 0 ? (
          <EmptyState
            title="No counterparts on this page"
            description="No current candidate pairs were returned for this contract and page."
          />
        ) : (
          <ul className="space-y-3">
            {rows.map((row) => {
              const id = row.left_id === marketId ? row.right_id : row.left_id;
              return (
                <li
                  key={row.id}
                  className="rounded-lg border border-border p-4"
                >
                  <MatchStatusBadge
                    status={row.status}
                    qualification={row.qualification}
                    relationship={row.relationship}
                    operatorVeto={row.operator_veto}
                    historical={row.historical}
                  />
                  <Link
                    href={`/matches/${encodeURIComponent(row.id)}`}
                    className="mt-2 block font-medium text-primary"
                  >
                    {index.get(id)?.title ?? id}
                  </Link>
                  <p className="mt-2 text-sm text-muted-foreground">
                    {row.reason}
                  </p>
                  {row.retrieval_limited && (
                    <p className="mt-2 text-sm text-amber-900">
                      Candidate retrieval was limited; other counterparts may
                      exist.
                    </p>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </QueryState>
      <nav
        aria-label="Counterpart pages"
        className="flex flex-wrap items-center gap-3"
      >
        <Button
          variant="outline"
          disabled={offset === 0 || matches.isPending}
          onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
        >
          Previous counterparts
        </Button>
        <span className="text-sm">
          Page {Math.floor(offset / PAGE_SIZE) + 1}
        </span>
        <Button
          variant="outline"
          disabled={rows.length < PAGE_SIZE || matches.isPending}
          onClick={() => setOffset(offset + PAGE_SIZE)}
        >
          Next counterparts
        </Button>
      </nav>
    </section>
  );
}
