import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Timestamp } from "@/components/timestamp";
import { formatMoney, formatQuantity } from "@/lib/decimal";
import type { Market, PotentialOpportunity } from "@/lib/api/schema";
import { reasonLabel, venueLabel } from "@/features/shared/status";

export function PotentialCard({
  item,
  markets,
  detail = false,
}: {
  item: PotentialOpportunity;
  markets: Map<string, Market>;
  detail?: boolean;
}) {
  return (
    <article className="rounded-xl border border-border bg-card p-5 sm:p-6">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="caution">Potential price gap</Badge>
        <span className="text-xs text-muted-foreground">
          Settlement {item.qualification.status}
        </span>
      </div>
      <h2 className="mt-3 text-lg font-semibold leading-7">
        <Link
          href={`/potential/${encodeURIComponent(item.id)}`}
          className="hover:text-primary"
        >
          {markets.get(item.market_ids[0])?.title ?? item.market_ids[0]}
        </Link>
      </h2>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        {item.market_ids.map((id, i) => (
          <div key={id} className="rounded-lg bg-muted p-3 text-sm">
            <p className="font-medium">
              {venueLabel(markets.get(id)?.venue ?? "unknown")} ·{" "}
              {item.outcomes[i].toUpperCase()}
            </p>
            <p className="mt-1 leading-6">{markets.get(id)?.title ?? id}</p>
          </div>
        ))}
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
        {[
          ["Gross ordinary-outcome gap", formatMoney(item.gross_spread)],
          ["Quantity", formatQuantity(item.quantity)],
          [
            "Known fee bound",
            item.fee_bound == null ? "Unknown" : formatMoney(item.fee_bound),
          ],
          [
            "Capital required",
            item.capital_required == null
              ? "Unknown"
              : formatMoney(item.capital_required),
          ],
        ].map(([label, value]) => (
          <div key={label}>
            <dt className="text-xs leading-5 text-muted-foreground">{label}</dt>
            <dd className="mt-1 font-semibold">{value}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 text-xs text-muted-foreground">
        Observed <Timestamp value={item.evaluated_at} /> · quotes expire{" "}
        <Timestamp value={item.valid_until} />
      </p>
      <ul className="mt-3 list-disc space-y-1 pl-5 text-sm leading-6 text-muted-foreground">
        {(detail
          ? item.unresolved_reasons
          : item.unresolved_reasons.slice(0, 3)
        ).map((reason) => (
          <li key={reason} className="break-words">
            {reasonLabel(reason)}
          </li>
        ))}
      </ul>
      {detail && (
        <>
          <p className="mt-4 text-sm">
            Acquisition cost: {formatMoney(item.acquisition_cost)}. Ordinary
            payout assumption: {formatMoney(item.ordinary_payout_assumption)}.
            Estimated ordinary net spread:{" "}
            {item.estimated_net_spread == null
              ? "Unknown"
              : formatMoney(item.estimated_net_spread)}
            .
          </p>
          <ul className="mt-3 list-disc space-y-1 pl-5 text-sm leading-6 text-muted-foreground">
            {(item.assumptions ?? []).map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </>
      )}
      <Link
        href={`/matches/${encodeURIComponent(item.match_id)}`}
        className="mt-4 inline-block text-sm font-semibold text-primary"
      >
        Inspect comparison and evidence
      </Link>
    </article>
  );
}
