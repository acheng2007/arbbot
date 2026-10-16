"use client";
import { Timestamp } from "@/components/timestamp";
import { QueryState } from "@/features/shared/query-state";
import { useApi } from "@/lib/query/hooks";
import { ClassificationPanel } from "./classification-panel";

export function ClassificationHistory({ matchId }: { matchId: string }) {
  const history = useApi("classificationHistory", {
    params: { match_id: matchId },
    query: { limit: 10 },
  });
  return (
    <QueryState
      isPending={history.isPending}
      error={history.error}
      loadingLabel="Loading matching history"
      onRetry={() => void history.refetch()}
    >
      <p className="mb-3 text-sm text-muted-foreground">
        Recorded model findings explain past inputs. They do not establish
        current eligibility or settlement verification.
      </p>
      {!history.data?.data.length && (
        <p className="text-sm">No matching assessments recorded.</p>
      )}
      <div className="space-y-3">
        {history.data?.data.map((run) => (
          <details key={run.id} className="rounded-lg border border-border p-3">
            <summary className="cursor-pointer text-sm font-medium">
              Historical finding ·{" "}
              <Timestamp
                value={
                  run.summary.completed_at ??
                  run.summary.started_at ??
                  new Date(0).toISOString()
                }
              />
            </summary>
            <p className="my-3 break-all text-xs text-muted-foreground">
              Input {run.input_hash} ·{" "}
              {run.applied
                ? "Applied to the recorded inputs"
                : "Audit only; not applied"}
            </p>
            <ClassificationPanel
              advice={{
                ...run.summary,
                state: "stale",
                supports_candidate: false,
              }}
            />
          </details>
        ))}
      </div>
    </QueryState>
  );
}
