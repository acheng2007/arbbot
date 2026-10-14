import type { ClassificationSummary } from "@/lib/api/schema";

export function ClassificationLabel({
  advice,
}: {
  advice?: ClassificationSummary | null;
}) {
  if (!advice) return <span>AI classification unconfigured</span>;
  if (advice.state === "fresh" && advice.supports_candidate) {
    return <span>AI suggests same event</span>;
  }
  return (
    <span>
      AI classification{" "}
      {advice.state === "fresh"
        ? (advice.event?.choice.replaceAll("_", " ") ?? "insufficient evidence")
        : advice.state}
    </span>
  );
}

export function ClassificationPanel({
  advice,
}: {
  advice?: ClassificationSummary | null;
}) {
  return (
    <section
      className="rounded-xl border border-border bg-card p-5 sm:p-6"
      aria-label="AI classification"
    >
      <h2 className="text-lg font-semibold">
        <ClassificationLabel advice={advice} />
      </h2>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">
        Advisory findings help identify pairs for review. Established event
        evidence, settlement verification, and executable financial checks
        remain required. Confidence is a model score, not measured accuracy.
      </p>
      {advice?.recorded && (
        <p className="mt-2 text-sm font-medium">
          Recorded model response, offline replay
        </p>
      )}
      {advice?.error && (
        <p role="status" className="mt-3 text-sm">
          Classification unavailable: {advice.error}. Exchange book polling
          continues independently.
        </p>
      )}
      {advice?.state === "pending" && (
        <p role="status" className="mt-3 text-sm">
          Waiting for classification. Existing contract evidence remains
          available.
        </p>
      )}
      {advice?.state === "stale" && (
        <p role="status" className="mt-3 text-sm">
          Previous advice expired or its source inputs changed. It no longer
          contributes to current suggestions.
        </p>
      )}
      {advice?.event && (
        <p className="mt-3 text-sm">
          Event finding: {advice.event.choice.replaceAll("_", " ")}. Model
          confidence score {advice.event.confidence.toFixed(2)}, same-event
          probability {(advice.event.probabilities.same_event ?? 0).toFixed(2)}.
        </p>
      )}
      {advice && (
        <dl className="mt-4 grid gap-2 text-xs text-muted-foreground sm:grid-cols-2">
          <div>
            <dt>Model</dt>
            <dd className="break-all">
              {advice.returned_model ?? advice.requested_model}
            </dd>
          </div>
          <div>
            <dt>Question version</dt>
            <dd>{advice.question_version}</dd>
          </div>
          <div>
            <dt>Completed</dt>
            <dd>{advice.completed_at ?? "Awaiting result"}</dd>
          </div>
          <div>
            <dt>Expires</dt>
            <dd>{advice.expires_at ?? "No cached result"}</dd>
          </div>
        </dl>
      )}
      <div className="mt-4 space-y-3">
        {Object.entries(advice?.clauses ?? {}).map(([clause, finding]) =>
          finding ? (
            <details
              key={clause}
              className="rounded-lg border border-border p-3"
            >
              <summary className="cursor-pointer text-sm font-medium">
                {clause.replaceAll("_", " ")}:{" "}
                {finding.choice.replaceAll("_", " ")}
              </summary>
              <p className="mt-2 text-xs text-muted-foreground">
                Model confidence score {finding.confidence.toFixed(2)}
              </p>
              {(finding.evidence_ids ?? []).length === 0 && (
                <p className="mt-2 text-sm">
                  No applicable supporting quotations captured.
                </p>
              )}
              {(finding.evidence_ids ?? []).map((id) => {
                const span = advice?.evidence?.find((entry) => entry.id === id);
                return span ? (
                  <figure key={id} className="mt-3">
                    <blockquote className="whitespace-pre-wrap break-words border-l-2 border-border pl-3 text-sm leading-6">
                      {span.quotation}
                    </blockquote>
                    <figcaption className="mt-1 break-words text-xs text-muted-foreground">
                      {span.side} contract, applicability: {span.applicability},
                      captured span {span.start}-{span.end}
                      {span.page ? `, page ${span.page}` : ""}
                      {span.artifact_id ? `, artifact ${span.artifact_id}` : ""}
                    </figcaption>
                  </figure>
                ) : null;
              })}
            </details>
          ) : null,
        )}
      </div>
      {advice && (advice.limitations ?? []).length > 0 && (
        <details className="mt-4 text-sm">
          <summary className="cursor-pointer font-medium">
            Coverage limitations
          </summary>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            {(advice.limitations ?? []).map((limit, i) => (
              <li key={i}>{limit}</li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
