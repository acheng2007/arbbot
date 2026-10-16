"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Timestamp } from "@/components/timestamp";
import { OriginBanner } from "@/components/data-origin";
import { QueryState } from "@/features/shared/query-state";
import { venueLabel } from "@/features/shared/status";
import { useApi } from "@/lib/query/hooks";

export function InventoryBrowser() {
  const params = useSearchParams(),
    router = useRouter();
  const offset = Math.max(0, Number(params.get("offset")) || 0),
    q = params.get("q") ?? "";
  const records = useApi("inventory", {
    query: { supported: false, limit: 25, offset, ...(q ? { q } : {}) },
  });
  const update = (values: Record<string, string>) => {
    const next = new URLSearchParams(params.toString());
    next.delete("offset");
    for (const [key, value] of Object.entries(values)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    router.replace(`/inventory?${next}`, { scroll: false });
  };
  return (
    <div className="space-y-5">
      <Link href="/markets" className="text-sm font-medium text-primary">
        Back to discoveries
      </Link>
      <h1 className="text-2xl font-semibold">Excluded source records</h1>
      <p className="text-sm leading-6 text-muted-foreground">
        These source records remain inspectable even when their instrument
        format is unsupported, their data is invalid, or they are closed or
        expired. They do not support current estimates.
      </p>
      <input
        type="search"
        aria-label="Search source identifiers"
        placeholder="Search source identifiers"
        value={q}
        onChange={(e) => update({ q: e.target.value })}
        className="h-11 w-full rounded-lg border border-border bg-card px-3 text-sm"
      />
      {records.data && <OriginBanner origin={records.data.origin} />}
      <QueryState
        isPending={records.isPending}
        error={records.error}
        loadingLabel="Loading excluded records"
        onRetry={() => void records.refetch()}
      >
        {!records.data?.data.length && (
          <p className="rounded-lg border border-border p-5 text-sm">
            No excluded records in this page of the captured catalog.
          </p>
        )}
        <ul className="space-y-3">
          {records.data?.data.map((record) => (
            <li
              key={record.observation_id}
              className="rounded-xl border border-border bg-card p-4"
            >
              <h2 className="break-all text-sm font-semibold">
                {venueLabel(record.venue)} · {record.external_id}
              </h2>
              <p className="mt-2 text-sm">
                {record.reason.replaceAll("_", " ")}
              </p>
              <p className="mt-2 text-xs text-muted-foreground">
                Observed <Timestamp value={record.observed_at} />
              </p>
              <details className="mt-3">
                <summary className="cursor-pointer text-sm font-medium">
                  Original source record
                </summary>
                <pre className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap break-all rounded-lg bg-muted p-3 text-xs">
                  {JSON.stringify(record.raw, null, 2)}
                </pre>
              </details>
            </li>
          ))}
        </ul>
      </QueryState>
      <nav aria-label="Inventory pages" className="flex justify-between gap-3">
        <Button
          variant="outline"
          disabled={!offset}
          onClick={() => update({ offset: String(Math.max(0, offset - 25)) })}
        >
          Previous
        </Button>
        <Button
          variant="outline"
          disabled={records.isPending || (records.data?.data.length ?? 0) < 25}
          onClick={() => update({ offset: String(offset + 25) })}
        >
          Next
        </Button>
      </nav>
    </div>
  );
}
