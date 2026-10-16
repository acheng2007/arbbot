"use client";

import { Disclosure } from "@/components/disclosure";
import { Timestamp } from "@/components/timestamp";
import { useApi } from "@/lib/query/hooks";
import type { Match } from "@/lib/api/schema";
import { reasonLabel } from "@/features/shared/status";

export function QualificationPanel({ match }: { match: Match }) {
  const query = useApi(
    "qualification",
    { params: { match_id: match.id } },
    { enabled: Boolean(match.qualification) && !match.historical },
  );
  const history = useApi(
    "qualificationHistory",
    { params: { match_id: match.id }, query: { limit: 10 } },
    { enabled: Boolean(match.qualification) },
  );
  const assessment = query.data?.data ?? match.qualification;
  return (
    <section
      aria-label="Automatic settlement assessment"
      className="rounded-xl border border-border bg-card p-5 sm:p-6"
    >
      <h2 className="text-lg font-semibold">Automatic settlement assessment</h2>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">
        Settlement verification is independent of model scores, current prices,
        fees, and account balances. Human approval is not required.
      </p>
      <p className="mt-3 text-sm font-medium capitalize">
        {match.historical
          ? "Historical assessment"
          : (assessment?.status?.replaceAll("_", " ") ??
            "Awaiting automatic assessment")}
      </p>
      {match.operator_veto && (
        <p className="mt-2 text-sm text-red-800">
          An operator veto blocks publication independently of semantic
          findings.
        </p>
      )}
      {!!assessment?.blocked_reasons?.length && (
        <ul className="mt-3 list-disc space-y-1 pl-5 text-sm leading-6 text-muted-foreground">
          {assessment.blocked_reasons.slice(0, 4).map((reason) => (
            <li className="break-words" key={reason}>
              {reasonLabel(reason)}
            </li>
          ))}
        </ul>
      )}
      {(assessment?.blocked_reasons?.length ?? 0) > 4 && (
        <Disclosure title="All assessment blockers">
          <ul className="list-disc space-y-2 pl-5 text-sm leading-6 text-muted-foreground">
            {assessment?.blocked_reasons?.map((reason) => (
              <li key={reason}>{reasonLabel(reason)}</li>
            ))}
          </ul>
        </Disclosure>
      )}
      {query.error && (
        <p role="status" className="mt-2 text-sm">
          Current assessment is unavailable. The displayed recorded state does
          not establish current eligibility.
        </p>
      )}
      {assessment?.completed_at && (
        <p className="mt-3 text-xs text-muted-foreground">
          Assessed <Timestamp value={assessment.completed_at} /> · policy{" "}
          {assessment.policy_version}
        </p>
      )}
      {!!match.retrieval_methods?.length && (
        <p className="mt-2 text-xs text-muted-foreground">
          Found through:{" "}
          {match.retrieval_methods
            .map((method) => method.replaceAll("_", " "))
            .join(", ")}
        </p>
      )}
      {!!match.settlement?.scenarios?.length && (
        <Disclosure title="Supported payout scenarios">
          <div className="mt-3 space-y-2">
            {match.settlement.scenarios.map((scenario) => (
              <div
                key={scenario.name}
                className="rounded-lg bg-muted p-3 text-xs"
              >
                <p className="font-medium">
                  {scenario.name.replaceAll("_", " ")}
                </p>
                <p>
                  Left YES {scenario.left_yes} / NO {scenario.left_no} · Right
                  YES {scenario.right_yes} / NO {scenario.right_no}
                </p>
              </div>
            ))}
          </div>
        </Disclosure>
      )}
      <Disclosure title="Assessment history">
        {history.isPending && match.qualification ? (
          <p className="mt-3 text-sm">Loading assessment history…</p>
        ) : null}
        {history.error ? (
          <p className="mt-3 text-sm">Assessment history unavailable.</p>
        ) : null}
        {!history.data?.data.length && !history.isPending ? (
          <p className="mt-3 text-sm text-muted-foreground">
            No automatic assessment history recorded.
          </p>
        ) : null}
        <ul className="mt-3 space-y-3">
          {history.data?.data.map((run) => (
            <li
              key={run.id}
              className="rounded-lg border border-border p-3 text-sm"
            >
              <p className="font-medium capitalize">
                {run.summary.status} ·{" "}
                <Timestamp value={run.summary.completed_at ?? run.started_at} />
              </p>
              <p className="mt-1 break-all text-xs text-muted-foreground">
                Historical input {run.input_hash}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                {run.summary.blocked_reasons
                  ?.map((reason) => reason.replaceAll("_", " "))
                  .join(" · ") ||
                  "Supported checks passed for these recorded inputs."}
              </p>
            </li>
          ))}
        </ul>
      </Disclosure>
    </section>
  );
}
