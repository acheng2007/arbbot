"use client";
import Link from "next/link";
import { Disclosure } from "@/components/disclosure";
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
  reasonLabel,
} from "@/features/shared/status";
import { MarketPrices } from "@/features/markets/market-prices";
import { ClassificationPanel } from "./classification-panel";
import { DifferenceTable } from "./difference-table";
import { ClassificationHistory } from "./classification-history";
import { QualificationPanel } from "./qualification-panel";
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
          <li key={issue}>{reasonLabel(issue)}</li>
        ))}
      </ul>
    </section>
  );
}

export function ComparisonDetail({
  matchId,
  historical = false,
}: {
  matchId: string;
  historical?: boolean;
}) {
  const matches = useApi("match", {
    params: { match_id: matchId },
    query: { historical },
  });
  const match = matches.data?.data;
  const withdrawnAdvice = useApi(
    "classificationDetail",
    { params: { match_id: matchId } },
    {
      enabled: matches.error?.failure === "not_found",
    },
  );
  const { index } = useMarketIndex(
    match ? [match.left_id, match.right_id] : [],
  );

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
        error={matches.error?.failure === "not_found" ? null : matches.error}
        loadingLabel="Loading contract comparison"
        onRetry={() => void matches.refetch()}
      >
        {!match ? (
          <div className="space-y-5">
            <EmptyState
              title="This pair is not available"
              description="The proposed pair may have been withdrawn, or the identifier in the address may be wrong."
            />
            <Link
              href={`/matches/${encodeURIComponent(matchId)}?historical=true`}
              className="inline-block text-sm font-medium text-primary"
            >
              Inspect recorded comparison
            </Link>
            {withdrawnAdvice.data && (
              <ClassificationPanel advice={withdrawnAdvice.data.data} />
            )}
          </div>
        ) : (
          (() => {
            const left = index.get(match.left_id);
            const right = index.get(match.right_id);
            return (
              <div className="space-y-7">
                <header className="space-y-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <MatchStatusBadge
                      status={match.status}
                      qualification={match.qualification}
                      relationship={match.relationship}
                      operatorVeto={match.operator_veto}
                      historical={match.historical}
                    />
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
                </header>

                <div className="grid gap-4 sm:grid-cols-2">
                  {[left, right].map(
                    (market) =>
                      market && (
                        <div
                          key={market.id}
                          className="rounded-xl border border-border bg-card p-4"
                        >
                          <Link
                            href={`/markets/${encodeURIComponent(market.id)}`}
                            className="mb-3 block text-sm font-semibold text-primary"
                          >
                            {venueLabel(market.venue)}
                          </Link>
                          <MarketPrices
                            marketId={market.id}
                            shortNo={market.venue === "polymarket_us"}
                          />
                        </div>
                      ),
                  )}
                </div>
                <Disclosure title="AI classification and matching rationale">
                  <p className="mb-4 text-sm text-muted-foreground">
                    Title similarity {match.similarity.toFixed(2)}.{" "}
                    {match.reason} Similarity alone does not establish
                    equivalence.
                  </p>
                  <ClassificationPanel advice={match.classification} />
                </Disclosure>

                <QualificationPanel match={match} />
                <Disclosure title="Matching assessment history">
                  <ClassificationHistory matchId={match.id} />
                </Disclosure>

                {match.relationship === "mismatch" && (
                  <div
                    role="status"
                    className="rounded-lg border border-red-300 bg-red-50 p-4 text-sm leading-6 text-red-950"
                  >
                    Supported checks found an event or settlement contradiction.
                    This comparison cannot support a qualified arbitrage
                    estimate.
                  </div>
                )}

                {match.comparison && (
                  <UnresolvedAssumptions issues={match.comparison.issues} />
                )}

                <Disclosure title="Settlement terms">
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
                </Disclosure>

                {match.review && (
                  <Disclosure title="Review evidence">
                    <ReviewPanel
                      review={match.review}
                      left={left}
                      right={right}
                    />
                  </Disclosure>
                )}
                {!match.review && (
                  <EmptyState
                    title="No review recorded"
                    description="Human review is optional. Current automatic evidence and settlement checks determine qualification independently of model scores and profitability."
                  />
                )}

                <Disclosure title="Source documents">
                  <div className="grid gap-4 lg:grid-cols-2">
                    {left && <SourceTerms market={left} />}
                    {right && <SourceTerms market={right} />}
                  </div>
                </Disclosure>
              </div>
            );
          })()
        )}
      </QueryState>
    </div>
  );
}
