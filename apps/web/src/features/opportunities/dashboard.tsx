"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { PotentialCard } from "./potential-card";
import { Disclosure } from "@/components/disclosure";
import type { Evaluation } from "@/lib/api/schema";
import Link from "next/link";
import { EmptyState } from "@/components/states";
import { OriginBanner } from "@/components/data-origin";
import { Timestamp } from "@/components/timestamp";
import { Badge } from "@/components/ui/badge";
import { formatMoney, formatQuantity } from "@/lib/decimal";
import { useApi } from "@/lib/query/hooks";
import { QueryState } from "@/features/shared/query-state";
import { useMarketIndex } from "@/features/shared/use-market-index";
import { OpportunityCard } from "./opportunity-card";
import { StreamStatusBanner } from "./stream-status";
import { useOpportunityStream } from "./use-stream";

function BlockedEvaluations() {
  const evaluations = useApi("evaluations", { query: { limit: 50 } });
  const blocked = (evaluations.data?.data ?? []).filter(
    (evaluation) => evaluation.blocked_reasons.length > 0,
  );
  if (evaluations.isPending || evaluations.error)
    return (
      <QueryState
        isPending={evaluations.isPending}
        error={evaluations.error}
        loadingLabel="Loading evaluations"
        onRetry={() => void evaluations.refetch()}
      >
        {null}
      </QueryState>
    );
  if (blocked.length === 0)
    return (
      <p className="text-sm text-muted-foreground">
        No blocked evaluations recorded.
      </p>
    );

  return (
    <section aria-labelledby="blocked-heading">
      <h2 id="blocked-heading" className="text-lg font-semibold">
        Evaluated but not tradable
      </h2>
      <p className="mt-1.5 mb-4 text-sm leading-6 text-muted-foreground">
        These pairs were evaluated and produced no opportunity. The reasons are
        recorded rather than hidden.
      </p>
      <ul className="space-y-3">
        {blocked.map((evaluation) => (
          <EvaluationRow key={evaluation.match_id} evaluation={evaluation} />
        ))}
      </ul>
    </section>
  );
}

function EvaluationRow({ evaluation }: { evaluation: Evaluation }) {
  const match = useApi("match", { params: { match_id: evaluation.match_id } });
  const { index } = useMarketIndex(
    match.data ? [match.data.data.left_id, match.data.data.right_id] : [],
  );
  const pair = match.data?.data;
  const title = pair
    ? `${index.get(pair.left_id)?.title ?? pair.left_id} against ${index.get(pair.right_id)?.title ?? pair.right_id}`
    : evaluation.match_id;
  return (
    <li className="rounded-lg border border-border bg-card p-4 sm:p-5">
      <Link
        href={`/matches/${encodeURIComponent(evaluation.match_id)}`}
        className="text-sm font-medium text-primary"
      >
        {title}
      </Link>
      <p className="mt-2 text-sm capitalize">
        {evaluation.status ?? "blocked"}
      </p>
      {evaluation.best_calculation && (
        <p className="mt-2 text-sm">
          Best estimated net result:{" "}
          {formatMoney(evaluation.best_calculation.net_profit)} on{" "}
          {formatQuantity(evaluation.best_calculation.quantity)} contracts.
        </p>
      )}
      <ul className="mt-2.5 list-disc space-y-1 pl-5 text-sm leading-6 text-muted-foreground">
        {evaluation.blocked_reasons.map((reason) => (
          <li key={reason} className="break-words">
            {reason}
          </li>
        ))}
      </ul>
    </li>
  );
}

export function OpportunityDashboard() {
  const router = useRouter();
  const params = useSearchParams();
  const potential = params.get("view") === "potential";
  const offset = Math.max(0, Number(params.get("offset")) || 0);
  const search = params.get("q") ?? "";
  const category = params.get("category") ?? "";
  const venue = params.get("venue") ?? "";
  const sort = params.get("sort") === "newest" ? "newest" : "value";
  const update = (changes: Record<string, string>) => {
    const next = new URLSearchParams(params.toString());
    next.delete("offset");
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    router.replace(`/opportunities?${next}`, { scroll: false });
  };
  const common = {
    limit: 25,
    offset,
    ...(search ? { q: search } : {}),
    ...(category ? { category_group: category } : {}),
    ...(venue ? { venue } : {}),
  };
  const opportunities = useApi(
    "opportunities",
    { query: { ...common, sort: sort === "newest" ? "newest" : "net_profit" } },
    { enabled: !potential },
  );
  const potentials = useApi(
    "potentialOpportunities",
    {
      query: { ...common, sort: sort === "newest" ? "newest" : "gross_spread" },
    },
    { enabled: potential },
  );
  const query = potential ? potentials : opportunities;
  const venues = useApi("venues");
  const { index } = useMarketIndex(
    potential
      ? (potentials.data?.data.flatMap((p) => p.market_ids) ?? [])
      : (opportunities.data?.data.flatMap((o) =>
          o.legs.map((leg) => leg.market_id),
        ) ?? []),
  );
  const stream = useOpportunityStream();
  const controls =
    "h-10 min-w-0 rounded-lg border border-border bg-card px-3 text-sm";
  return (
    <div className="space-y-5">
      <div
        className="flex gap-6 border-b border-border"
        aria-label="Opportunity views"
      >
        {[
          ["qualified", "Qualified"],
          ["potential", "Potential"],
        ].map(([view, label]) => (
          <button
            key={view}
            onClick={() => update({ view })}
            aria-pressed={(potential ? "potential" : "qualified") === view}
            className={`border-b-2 pb-3 text-sm font-semibold ${(potential ? "potential" : "qualified") === view ? "border-primary text-foreground" : "border-transparent text-muted-foreground"}`}
          >
            {label}
          </button>
        ))}
      </div>
      <p className="text-sm leading-6 text-muted-foreground">
        {potential
          ? "Ordinary-outcome price gaps. Settlement compatibility or financial inputs remain unresolved; these are not qualified profit estimates."
          : "Positive worst-case conditional estimates after supported costs and settlement checks. Quotes can change and cross-venue fills are not atomic."}
      </p>
      <div className="flex flex-wrap gap-2">
        <input
          aria-label="Search opportunities"
          placeholder="Search events"
          type="search"
          value={search}
          maxLength={200}
          onChange={(e) => update({ q: e.target.value })}
          className={`${controls} w-full sm:flex-1`}
        />
        <select
          aria-label="Opportunity category"
          value={category}
          onChange={(e) => update({ category: e.target.value })}
          className={controls}
        >
          <option value="">All categories</option>
          {["politics", "economics", "sports", "other", "unknown"].map((c) => (
            <option value={c} key={c}>
              {c[0].toUpperCase() + c.slice(1)}
            </option>
          ))}
        </select>
        <select
          aria-label="Opportunity venue"
          value={venue}
          onChange={(e) => update({ venue: e.target.value })}
          className={controls}
        >
          <option value="">All venues</option>
          {venues.data?.data
            .filter((v) => v.enabled)
            .map((v) => (
              <option key={v.id} value={v.id}>
                {v.name}
              </option>
            ))}
        </select>
        <select
          aria-label="Opportunity sort"
          value={sort}
          onChange={(e) => update({ sort: e.target.value })}
          className={controls}
        >
          <option value="value">
            Largest {potential ? "gross gap" : "net estimate"}
          </option>
          <option value="newest">Newest</option>
        </select>
      </div>
      {query.data && <OriginBanner origin={query.data.origin} />}
      <StreamStatusBanner state={stream} />
      <QueryState
        isPending={query.isPending}
        error={query.error}
        loadingLabel={
          potential ? "Loading potential price gaps" : "Loading opportunities"
        }
        onRetry={() => void query.refetch()}
      >
        {query.data?.data.length === 0 ? (
          <EmptyState
            title={
              potential
                ? "No potential price gaps right now"
                : "No opportunities right now"
            }
            description={
              potential
                ? "No current counterpart with aligned ordinary outcomes and fresh supported depth has a positive gross gap. Browse Discoveries to inspect suggestions and missing inputs."
                : "No current pair passes every settlement and financial check with a positive estimate. This may reflect missing evidence, unavailable quotes or costs, or unprofitable prices. Browse Potential and Discoveries to see the difference."
            }
          />
        ) : (
          <ul className="space-y-5">
            {potential
              ? potentials.data?.data.map((item) => (
                  <li key={item.id}>
                    <PotentialCard item={item} markets={index} />
                  </li>
                ))
              : opportunities.data?.data.map((opportunity) => (
                  <li
                    key={`${opportunity.match_id}:${opportunity.legs.map((l) => `${l.market_id}:${l.outcome}`).join("|")}`}
                  >
                    <OpportunityCard
                      opportunity={opportunity}
                      markets={index}
                    />
                  </li>
                ))}
          </ul>
        )}
      </QueryState>
      <nav
        aria-label="Opportunity pages"
        className="flex items-center justify-between gap-3 border-t border-border pt-4"
      >
        <span className="text-xs text-muted-foreground">
          Page {Math.floor(offset / 25) + 1}
        </span>
        <div className="flex gap-2">
          <Button
            variant="outline"
            disabled={!offset}
            onClick={() => update({ offset: String(Math.max(0, offset - 25)) })}
          >
            Previous
          </Button>
          <Button
            variant="outline"
            disabled={query.isPending || (query.data?.data.length ?? 0) < 25}
            onClick={() => update({ offset: String(offset + 25) })}
          >
            Next
          </Button>
        </div>
      </nav>
      <p className="text-xs leading-5 text-muted-foreground">
        Account eligibility, balances, inventory, borrowing, and
        account-specific charges remain unverified assumptions.
      </p>
      {!potential && (
        <>
          <Disclosure title="Evaluated but not tradable">
            <BlockedEvaluations />
          </Disclosure>
          <Disclosure title="Recently expired">
            <RecentHistory />
          </Disclosure>
        </>
      )}
    </div>
  );
}

function RecentHistory() {
  const history = useApi("history", { query: { limit: 20 } });
  const entries = history.data?.data ?? [];
  if (history.isPending || history.error)
    return (
      <QueryState
        isPending={history.isPending}
        error={history.error}
        loadingLabel="Loading history"
        onRetry={() => void history.refetch()}
      >
        {null}
      </QueryState>
    );
  if (entries.length === 0)
    return (
      <p className="text-sm text-muted-foreground">
        No expired opportunities recorded.
      </p>
    );

  return (
    <section aria-labelledby="history-heading">
      <h2 id="history-heading" className="text-lg font-semibold">
        Recently expired
      </h2>
      <p className="mt-1.5 mb-4 text-sm leading-6 text-muted-foreground">
        Previous evaluations kept for audit. These quotes have expired and are
        not actionable.
      </p>
      <ul className="space-y-3">
        {entries.map((entry) => (
          <li
            key={entry.id}
            className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-card p-4"
          >
            <Badge tone="neutral">Expired</Badge>
            <Link
              href={`/opportunities/${encodeURIComponent(entry.id)}`}
              className="text-sm font-medium text-primary"
            >
              {formatMoney(entry.net_profit)} estimated on{" "}
              {formatQuantity(entry.quantity)} contracts
            </Link>
            <span className="text-sm text-muted-foreground">
              evaluated <Timestamp value={entry.evaluated_at} />
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
