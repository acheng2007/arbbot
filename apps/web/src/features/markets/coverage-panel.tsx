"use client";

import Link from "next/link";
import { Timestamp } from "@/components/timestamp";
import { useApi } from "@/lib/query/hooks";
import { venueLabel } from "@/features/shared/status";
import { categoryQuery, type MarketFilters } from "./filters";

export function CoveragePanel({ filters }: { filters: MarketFilters }) {
  const coverage = useApi("discoveryCoverage", {
    query: {
      ...(filters.venue ? { venue: filters.venue } : {}),
      ...(filters.search ? { q: filters.search } : {}),
      ...(filters.status ? { status: filters.status } : {}),
      ...categoryQuery(filters.category),
      exclude_mismatch: !filters.relationship,
      exclude_rejected: !filters.relationship,
      ...(filters.relationship === "history" ? { historical: true } : {}),
      ...(filters.relationship && filters.relationship !== "history"
        ? { relationship: filters.relationship }
        : {}),
    },
  });
  const data = coverage.data?.data;
  if (!data)
    return (
      <p role="status" className="text-xs text-muted-foreground">
        {coverage.error
          ? "Coverage summary unavailable. Browsing remains available."
          : "Checking discovery coverage…"}
      </p>
    );
  return (
    <section
      aria-label="Discovery coverage"
      className="rounded-xl border border-border bg-card"
    >
      <details>
        <summary className="flex cursor-pointer flex-wrap items-center justify-between gap-2 px-4 py-3 text-xs font-medium">
          <span className="tabular-nums">
            {data.contracts} contracts · {data.comparisons} comparisons ·{" "}
            {data.verified} verified
          </span>
          <span className="sr-only text-muted-foreground sm:not-sr-only">
            Coverage by category and venue
          </span>
        </summary>
        <div className="border-t border-border p-4 sm:p-5">
          <dl className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
            {[
              ["Contracts", data.contracts],
              ["Comparisons", data.comparisons],
              ["Unverified", data.unverified],
              ["Verified", data.verified],
            ].map(([label, value]) => (
              <div key={label}>
                <dt className="text-muted-foreground">{label}</dt>
                <dd className="mt-1 text-xl font-semibold tabular-nums">
                  {value}
                </dd>
              </div>
            ))}
          </dl>
          <p className="mt-3 text-xs leading-5 text-muted-foreground">
            Semantic search: {data.retrieval.state}. {data.retrieval.indexed} of{" "}
            {data.retrieval.catalog} contracts indexed.
            {data.retrieval.error
              ? " Keyword retrieval continues while semantic search recovers."
              : ""}
            {data.catalogs.some((c) => !c.coverage_complete)
              ? " Catalog traversal is incomplete."
              : ""}
            {data.excluded_instruments > 0
              ? ` ${data.excluded_instruments} unsupported or excluded instruments retained in inventory.`
              : ""}
          </p>
          <p className="mt-2 text-xs leading-5 text-muted-foreground">
            Pair assessor: {data.model_state ?? "pending"} ·{" "}
            {data.queued_pairs ?? 0} queued. Coverage sampled{" "}
            <Timestamp value={data.as_of} />.
          </p>
          {data.excluded_instruments > 0 && (
            <Link
              href="/inventory"
              className="mt-3 inline-block text-sm font-medium text-primary"
            >
              Inspect excluded source records
            </Link>
          )}
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            {data.groups.map((group) => (
              <div
                key={`${group.venue}:${group.category}`}
                className="rounded-lg border border-border p-3 text-sm"
              >
                <h3 className="font-semibold capitalize">
                  {group.category} · {venueLabel(group.venue)}
                </h3>
                <p className="mt-1 text-muted-foreground">
                  {group.contracts} contracts · {group.with_counterparts} with
                  counterparts · {group.assessed} assessed · {group.fresh_books}{" "}
                  monitored with healthy books
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {group.incomplete} incomplete · {group.mismatch} mismatched ·{" "}
                  {group.verified} verified
                </p>
                {Object.entries(group.blockers ?? {})
                  .slice(0, 3)
                  .map(([reason, count]) => (
                    <p
                      className="mt-1 break-words text-xs text-muted-foreground"
                      key={reason}
                    >
                      {reason.replaceAll("_", " ")}: {count}
                    </p>
                  ))}
              </div>
            ))}
          </div>
          <p className="mt-3 text-xs leading-5 text-muted-foreground">
            Counts describe this filtered catalog and current comparisons, not
            exhaustive exchange overlap. Contracts without counterparts may
            await assessment or a later retrieval pass. Lack of a venue offering
            is not a matching failure.
          </p>
        </div>
      </details>
    </section>
  );
}
