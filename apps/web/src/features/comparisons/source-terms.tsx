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
  return (
    <section className="rounded-xl border border-border bg-card p-5 sm:p-6">
      <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
        {venueLabel(market.venue)} original terms
      </h3>
      <p className="mt-2 font-medium leading-6">{market.title}</p>
      <div className="mt-4">
        <SourceQuote>{market.rules}</SourceQuote>
      </div>
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
