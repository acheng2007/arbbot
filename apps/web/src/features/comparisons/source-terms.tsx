import type { Market } from "@/lib/api/schema";
import { Timestamp } from "@/components/timestamp";
import { venueLabel } from "@/features/shared/status";

/**
 * Renders exchange-authored text as plain text. React escapes it, and nothing
 * here interprets markup, so venue rules cannot inject content into the page.
 */
export function SourceQuote({ children }: { children: string }) {
  return (
    <blockquote className="border-l-2 border-border pl-3 text-sm leading-6 whitespace-pre-wrap text-muted-foreground">
      {children}
    </blockquote>
  );
}

export function SourceTerms({ market }: { market: Market }) {
  const details = market.settlement_details ?? {};
  const provenance = Array.isArray(details.source_text_provenance)
    ? details.source_text_provenance.filter(
        (entry): entry is Record<string, unknown> =>
          typeof entry === "object" && entry !== null,
      )
    : [];
  const texts = Object.entries(details).filter(
    ([key, value]) =>
      key.startsWith("source_text_") && typeof value === "string",
  ) as [string, string][];
  const issues = Array.isArray(details.source_issues)
    ? details.source_issues.filter(
        (issue): issue is string => typeof issue === "string",
      )
    : [];
  return (
    <section className="rounded-xl border border-border bg-card p-5 sm:p-6">
      <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
        {venueLabel(market.venue)} original terms
      </h3>
      <p className="mt-2 font-medium leading-6">{market.title}</p>
      <div className="mt-4">
        <SourceQuote>{market.rules}</SourceQuote>
      </div>
      {issues.length > 0 && (
        <div className="mt-4 rounded-md border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950">
          <p className="font-semibold">
            Settlement evidence remains incomplete
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            {issues.map((issue) => (
              <li key={issue}>{issue.replaceAll("_", " ")}</li>
            ))}
          </ul>
        </div>
      )}
      {texts.map(([key, text]) => (
        <details key={key} className="mt-4 rounded-md border border-border p-4">
          <summary className="cursor-pointer text-sm font-semibold">
            Captured {key.slice("source_text_".length).replaceAll("_", " ")}{" "}
            text
          </summary>
          <p className="my-3 text-xs text-muted-foreground">
            Derived from captured source bytes. Capture does not establish
            contract equivalence.
          </p>
          {provenance
            .filter(
              (entry) =>
                "source_text_" + entry.label === key &&
                typeof entry.artifact_id === "string",
            )
            .map((entry) => (
              <a
                key={String(entry.artifact_id)}
                className="mb-3 block break-all text-xs text-primary underline"
                href={`/api/data/sourceText?artifact_id=${encodeURIComponent(String(entry.artifact_id))}`}
                target="_blank"
                rel="noreferrer"
              >
                Inspect captured text and provenance:{" "}
                {String(entry.artifact_id).slice(0, 16)}
              </a>
            ))}
          <div className="max-h-96 overflow-y-auto">
            <SourceQuote>{text}</SourceQuote>
          </div>
        </details>
      ))}
      <dl className="mt-5 grid gap-3 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-muted-foreground">Venue identifier</dt>
          <dd className="mt-0.5 font-mono text-xs break-all">
            {market.external_id}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Settlement asset</dt>
          <dd className="mt-0.5">{market.settlement_asset}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Closes</dt>
          <dd className="mt-0.5">
            <Timestamp value={market.closes_at} />
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Terms version</dt>
          <dd className="mt-0.5 font-mono text-xs break-all">
            {market.terms_hash.slice(0, 16)}...
          </dd>
        </div>
      </dl>
    </section>
  );
}
