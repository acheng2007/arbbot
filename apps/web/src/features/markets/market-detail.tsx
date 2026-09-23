"use client";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/states";
import { OriginBanner } from "@/components/data-origin";
import { Age } from "@/components/freshness";
import { describeFailure } from "@/lib/api/errors";
import { useApi } from "@/lib/query/hooks";
import type { Extraction } from "@/lib/api/schema";
import { QueryState } from "@/features/shared/query-state";
import { fieldLabel, venueLabel } from "@/features/shared/status";
import { SourceQuote, SourceTerms } from "@/features/comparisons/source-terms";
import { QuoteHealth } from "./quote-health";

const EXTRACTION_STATUS = {
  partial: { tone: "caution", label: "Partially extracted" },
  unsupported: { tone: "critical", label: "Not supported" },
  ambiguous: { tone: "critical", label: "Ambiguous" },
} as const;

function ExtractedTerms({ extraction }: { extraction: Extraction }) {
  const facts = Object.entries(extraction.definition.facts);
  const status = EXTRACTION_STATUS[extraction.status];

  return (
    <section className="rounded-xl border border-border bg-card p-5 sm:p-6">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="mr-auto text-lg font-semibold">Extracted terms</h3>
        <Badge tone={status.tone}>{status.label}</Badge>
        <Badge tone="neutral">{extraction.definition.extractor}</Badge>
      </div>

      {extraction.issues.length > 0 && (
        <ul className="mt-4 list-disc space-y-1.5 rounded-md border border-amber-300 bg-amber-50 p-4 pl-8 text-sm leading-6 text-amber-950">
          {extraction.issues.map((issue) => (
            <li key={issue}>{issue}</li>
          ))}
        </ul>
      )}

      {extraction.missing_fields.length > 0 && (
        <div className="mt-4">
          <h4 className="text-sm font-semibold">Fields not determined</h4>
          <p className="mt-1.5 text-sm leading-6 text-muted-foreground">
            These terms could not be read from the published text. A missing
            field never counts toward equivalence.
          </p>
          <ul className="mt-2.5 flex flex-wrap gap-2">
            {extraction.missing_fields.map((field) => (
              <li key={field}>
                <Badge tone="caution">{fieldLabel(field)}</Badge>
              </li>
            ))}
          </ul>
        </div>
      )}

      <dl className="mt-5 space-y-4">
        {facts.map(([field, fact]) =>
          fact ? (
            <div key={field} className="border-t border-border pt-4">
              <dt className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                {fieldLabel(field)}
              </dt>
              <dd className="mt-1.5">
                <p className="text-sm font-medium">{fact.value}</p>
                <div className="mt-1.5">
                  <SourceQuote>{fact.quote}</SourceQuote>
                </div>
              </dd>
            </div>
          ) : null,
        )}
      </dl>
    </section>
  );
}

export function MarketDetail({ marketId }: { marketId: string }) {
  const market = useApi("market", { params: { market_id: marketId } });
  const extraction = useApi("extraction", { params: { market_id: marketId } });
  const book = useApi(
    "book",
    { params: { market_id: marketId } },
    {
      refetchInterval: 5000,
    },
  );

  return (
    <div className="space-y-7">
      <Link
        href="/markets"
        className="inline-flex items-center gap-1.5 text-sm font-medium text-primary"
      >
        <ArrowLeft aria-hidden="true" className="size-4" />
        All markets
      </Link>

      {market.data && <OriginBanner origin={market.data.origin} />}

      <QueryState
        isPending={market.isPending}
        error={market.error}
        loadingLabel="Loading market"
        onRetry={() => void market.refetch()}
      >
        {market.data && (
          <div className="space-y-7">
            <header className="space-y-4">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="neutral">
                  {venueLabel(market.data.data.venue)}
                </Badge>
                <Badge
                  tone={
                    market.data.data.status === "open" ? "positive" : "neutral"
                  }
                >
                  {market.data.data.status === "open" ? "Open" : "Closed"}
                </Badge>
                <Badge
                  tone={
                    market.data.data.mode === "live" ? "positive" : "caution"
                  }
                >
                  {market.data.data.mode === "live"
                    ? "Live feed"
                    : "Simulation"}
                </Badge>
                <Age at={market.data.data.observed_at} label="Observed" />
              </div>
              <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
                {market.data.data.title}
              </h1>
            </header>

            <QueryState
              isPending={book.isPending}
              error={book.error}
              loadingLabel="Loading order book"
              onRetry={() => void book.refetch()}
            >
              {book.data && <QuoteHealth book={book.data.data} />}
            </QueryState>

            <SourceTerms market={market.data.data} />

            {extraction.isError ? (
              <EmptyState
                title="No extracted terms"
                description={describeFailure(extraction.error)}
              />
            ) : (
              extraction.data && (
                <ExtractedTerms extraction={extraction.data.data} />
              )
            )}
          </div>
        )}
      </QueryState>
    </div>
  );
}
