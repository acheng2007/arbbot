"use client";
import Link from "next/link";
import { ArrowLeft, CircleAlert } from "lucide-react";
import { EmptyState } from "@/components/states";
import { OriginBanner } from "@/components/data-origin";
import { useApi } from "@/lib/query/hooks";
import { QueryState } from "@/features/shared/query-state";
import { useMarketIndex } from "@/features/shared/use-market-index";
import {
  ComparisonStatusBadge,
  MatchStatusBadge,
  venueLabel,
} from "@/features/shared/status";
import { DifferenceTable } from "./difference-table";
import { ReviewPanel } from "./review-panel";
import { SourceTerms } from "./source-terms";

function UnresolvedAssumptions({ issues }: { issues: string[] }) {
  if (issues.length === 0) return null;
  return (
    <section className="rounded-xl border border-amber-300 bg-amber-50 p-5 sm:p-6">
      <h3 className="flex items-center gap-2 font-semibold text-amber-950">
        <CircleAlert aria-hidden="true" className="size-4" />
        Unresolved assumptions
      </h3>
      <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-6 text-amber-950">
        {issues.map((issue) => (
          <li key={issue}>{issue}</li>
        ))}
      </ul>
    </section>
  );
}

export function ComparisonDetail({ matchId }: { matchId: string }) {
  const matches = useApi("matches", { query: { limit: 200 } });
  const { index } = useMarketIndex();
  const match = matches.data?.data.find((entry) => entry.id === matchId);

  return (
    <div className="space-y-7">
      <Link
        href="/matches"
        className="inline-flex items-center gap-1.5 text-sm font-medium text-primary"
      >
        <ArrowLeft aria-hidden="true" className="size-4" />
        All proposed pairs
      </Link>

      {matches.data && <OriginBanner origin={matches.data.origin} />}

      <QueryState
        isPending={matches.isPending}
        error={matches.error}
        loadingLabel="Loading contract comparison"
        onRetry={() => void matches.refetch()}
      >
        {!match ? (
          <EmptyState
            title="This pair is not available"
            description="The proposed pair may have been withdrawn, or the identifier in the address may be wrong."
          />
        ) : (
          (() => {
            const left = index.get(match.left_id);
            const right = index.get(match.right_id);
            return (
              <div className="space-y-7">
                <header className="space-y-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <MatchStatusBadge status={match.status} />
                    {match.comparison && (
                      <ComparisonStatusBadge status={match.comparison.status} />
                    )}
                  </div>
                  <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
                    {left?.title ?? match.left_id}
                  </h1>
                  <p className="text-base leading-7 text-muted-foreground">
                    Compared against{" "}
                    <span className="font-medium text-foreground">
                      {right?.title ?? match.right_id}
                    </span>{" "}
                    on {right ? venueLabel(right.venue) : "the other venue"}.
                  </p>
                  <p className="rounded-lg border border-border bg-card p-4 text-sm leading-6">
                    <span className="font-medium">
                      Title similarity {match.similarity.toFixed(2)}.
                    </span>{" "}
                    Similarity ranks candidates for review and is never evidence
                    of equivalent settlement. {match.reason}
                  </p>
                </header>

                {match.comparison?.same_event === false && (
                  <div
                    role="status"
                    className="rounded-lg border border-red-300 bg-red-50 p-4 text-sm leading-6 text-red-950"
                  >
                    These contracts have not been established as describing the
                    same event. Any price difference between them is not
                    arbitrage.
                  </div>
                )}

                {match.comparison && (
                  <UnresolvedAssumptions issues={match.comparison.issues} />
                )}

                <section>
                  <h2 className="text-lg font-semibold">Settlement terms</h2>
                  <p className="mt-1.5 mb-4 text-sm leading-6 text-muted-foreground">
                    Each field shows the extracted interpretation and the exact
                    text it came from.
                  </p>
                  {match.comparison ? (
                    <DifferenceTable
                      comparison={match.comparison}
                      leftLabel={
                        left ? venueLabel(left.venue) : "Left contract"
                      }
                      rightLabel={
                        right ? venueLabel(right.venue) : "Right contract"
                      }
                    />
                  ) : (
                    <EmptyState
                      title="No term comparison recorded"
                      description="Settlement terms have not been extracted for this pair, so equivalence cannot be assessed."
                    />
                  )}
                </section>

                {match.review && (
                  <ReviewPanel
                    review={match.review}
                    left={left}
                    right={right}
                  />
                )}
                {!match.review && (
                  <EmptyState
                    title="No review recorded"
                    description="No reviewer has examined this pair. It cannot support an executable arbitrage opportunity until the settlement terms are verified."
                  />
                )}

                <section className="space-y-4">
                  <h2 className="text-lg font-semibold">Source documents</h2>
                  <div className="grid gap-4 lg:grid-cols-2">
                    {left && <SourceTerms market={left} />}
                    {right && <SourceTerms market={right} />}
                  </div>
                </section>
              </div>
            );
          })()
        )}
      </QueryState>
    </div>
  );
}
