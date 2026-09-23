"use client";
import { TriangleAlert } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Timestamp } from "@/components/timestamp";
import { useNow } from "@/components/freshness";
import { formatMoney, formatQuantity } from "@/lib/decimal";
import type { CostPolicy, Market, Review } from "@/lib/api/schema";
import { venueLabel } from "@/features/shared/status";

function Callout({ children }: { children: React.ReactNode }) {
  return (
    <p
      role="status"
      className="flex items-start gap-2.5 rounded-md border border-amber-300 bg-amber-50 p-3.5 text-sm leading-6 text-amber-950"
    >
      <TriangleAlert aria-hidden="true" className="mt-1 size-4 shrink-0" />
      <span>{children}</span>
    </p>
  );
}

function CostSummary({
  label,
  costs,
  asset,
}: {
  label: string;
  costs: CostPolicy;
  asset: string;
}) {
  return (
    <div className="rounded-lg border border-border p-4">
      <h4 className="text-sm font-semibold">{label}</h4>
      <dl className="mt-3 space-y-2 text-sm">
        {[
          ["Fee per contract", formatMoney(costs.fee_per_contract, asset)],
          ["Fixed fee", formatMoney(costs.fixed_fee, asset)],
          ["Minimum order size", formatQuantity(costs.min_order_size)],
          ["Minimum notional", formatMoney(costs.min_notional, asset)],
        ].map(([term, value]) => (
          <div key={term} className="flex justify-between gap-4">
            <dt className="text-muted-foreground">{term}</dt>
            <dd className="tabular-nums">{value}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 text-xs leading-5 text-muted-foreground">
        {costs.evidence}
      </p>
    </div>
  );
}

type Props = {
  review: Review;
  left?: Market;
  right?: Market;
};

/**
 * A recorded review, shown read-only. Approval is only meaningful against the
 * exact contract terms that were reviewed, so this panel checks the reviewed
 * terms hashes against the current ones and flags expiry.
 */
export function ReviewPanel({ review, left, right }: Props) {
  const now = useNow();
  const expiry = Date.parse(review.expires_at);
  const expired = now !== null && !Number.isNaN(expiry) && expiry <= now;

  const changed = [
    left && left.terms_hash !== review.left_terms_hash
      ? venueLabel(left.venue)
      : null,
    right && right.terms_hash !== review.right_terms_hash
      ? venueLabel(right.venue)
      : null,
  ].filter((value): value is string => value !== null);

  return (
    <section className="space-y-5 rounded-xl border border-border bg-card p-5 sm:p-6">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="mr-auto text-lg font-semibold">Recorded review</h3>
        <Badge tone={review.status === "verified" ? "positive" : "critical"}>
          {review.status === "verified" ? "Verified" : "Rejected"}
        </Badge>
        {expired ? (
          <Badge tone="critical">Approval expired</Badge>
        ) : (
          <Badge tone="neutral">
            Expires <Timestamp value={review.expires_at} />
          </Badge>
        )}
      </div>

      {expired && (
        <Callout>
          This approval expired on <Timestamp value={review.expires_at} />. It
          no longer supports treating the pair as equivalent until a reviewer
          renews it.
        </Callout>
      )}
      {changed.length > 0 && (
        <Callout>
          The published terms changed on {changed.join(" and ")} after this
          review was recorded. The approval applies to the reviewed version
          only.
        </Callout>
      )}

      <dl className="space-y-4 text-sm leading-6">
        {[
          ["Reviewer", review.reviewer],
          ["Rationale", review.rationale],
          ["Resolution sources", review.resolution_sources],
          ["Deadlines and time zones", review.deadlines_and_timezones],
          ["Cancellation and exceptions", review.cancellation_and_exceptions],
        ].map(([term, value]) => (
          <div key={term}>
            <dt className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              {term}
            </dt>
            <dd className="mt-1">{value}</dd>
          </div>
        ))}
      </dl>

      <div>
        <h4 className="text-sm font-semibold">Settlement outcomes checked</h4>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[26rem] text-sm">
            <caption className="sr-only">
              How each contract settles under every reviewed outcome
            </caption>
            <thead>
              <tr className="border-b border-border text-left text-muted-foreground">
                <th scope="col" className="py-2 pr-4 font-medium">
                  Outcome
                </th>
                <th scope="col" className="py-2 pr-4 font-medium">
                  {left ? venueLabel(left.venue) : "Left"} yes
                </th>
                <th scope="col" className="py-2 font-medium">
                  {right ? venueLabel(right.venue) : "Right"} yes
                </th>
              </tr>
            </thead>
            <tbody>
              {review.scenarios.map((scenario) => (
                <tr key={scenario.name} className="border-b border-border/60">
                  <td className="py-2.5 pr-4">{scenario.name}</td>
                  <td className="py-2.5 pr-4 tabular-nums">
                    {scenario.left_yes}
                  </td>
                  <td className="py-2.5 tabular-nums">{scenario.right_yes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <CostSummary
          label={`${left ? venueLabel(left.venue) : "Left"} costs`}
          costs={review.left_costs}
          asset={left?.settlement_asset ?? "USD"}
        />
        <CostSummary
          label={`${right ? venueLabel(right.venue) : "Right"} costs`}
          costs={review.right_costs}
          asset={right?.settlement_asset ?? "USD"}
        />
      </div>
    </section>
  );
}
