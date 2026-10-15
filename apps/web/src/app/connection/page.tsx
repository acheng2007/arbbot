"use client";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { ErrorState, LoadingState, StaleNotice } from "@/components/states";
export default function Connection() {
  const query = useQuery({
    queryKey: ["backend-connection"],
    queryFn: async ({ signal }) => {
      const response = await fetch("/api/connection", { signal });
      if (!response.ok) throw new Error("Backend unavailable");
      return response.json() as Promise<{
        status: "ok";
        mode: "simulation" | "live";
      }>;
    },
    retry: false,
  });
  return (
    <section className="space-y-6">
      <div>
        <p className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-primary">
          Workspace status
        </p>
        <h1 className="text-3xl font-semibold tracking-tight">
          API connection
        </h1>
        <p className="mt-4 max-w-2xl leading-7 text-muted-foreground">
          Check whether the configured backend responds. This check does not
          establish exchange health, quote freshness, or execution readiness.
        </p>
      </div>
      {query.isPending ? (
        <LoadingState label="Checking API connection" />
      ) : query.isError ? (
        <ErrorState
          title="Backend unavailable"
          description="The connection could not be verified. Check the backend service and its configuration, then try again."
          onRetry={() => void query.refetch()}
        />
      ) : (
        <div className="rounded-lg border border-border bg-card p-6">
          <p role="status" className="font-semibold">
            Backend reachable
          </p>
          <p className="mt-3 text-sm">
            Reported mode:{" "}
            <strong>
              {query.data.mode === "simulation" ? "Simulation" : "Live"}
            </strong>
          </p>
          <p className="mt-2 text-sm text-muted-foreground">
            {query.data.mode === "simulation"
              ? "Simulation data is synthetic and is not live market data."
              : "Live ingestion is configured. Check individual markets for quote freshness."}
          </p>
          <Button
            variant="outline"
            className="mt-5"
            disabled={query.isFetching}
            onClick={() => void query.refetch()}
          >
            {query.isFetching ? "Checking…" : "Check again"}
          </Button>
        </div>
      )}
      {query.isError && query.data && (
        <StaleNotice>
          The previous connection result is out of date and cannot be relied on.
        </StaleNotice>
      )}
    </section>
  );
}
