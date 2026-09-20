import Link from "next/link";
import {
  ArrowRight,
  Files,
  GitCompareArrows,
  ChartNoAxesCombined,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/states";
export default function Home() {
  return (
    <div className="space-y-9">
      <section>
        <p className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-primary">
          Research workspace
        </p>
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
          A clearer view of every opportunity.
        </h1>
        <p className="mt-4 max-w-2xl text-base leading-7 text-muted-foreground">
          Follow the evidence from market terms to executable quotes. Compare
          contracts, inspect assumptions, and understand the risks behind an
          estimate.
        </p>
      </section>
      <section className="rounded-xl border border-border bg-card p-6 sm:p-8">
        <div className="flex flex-wrap items-start justify-between gap-5">
          <div>
            <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Workspace status
            </span>
            <h2 className="mt-3 text-xl font-semibold">
              Your foundation is ready
            </h2>
            <p className="mt-2 max-w-xl text-sm leading-6 text-muted-foreground">
              Market data and opportunity views are not connected in this
              preview. No live quotes, matches, or profit estimates are
              displayed.
            </p>
          </div>
          <span className="rounded-full bg-muted px-3 py-1.5 text-xs font-medium">
            No market data
          </span>
        </div>
        <Button asChild className="mt-6">
          <Link href="/connection">
            Check API connection
            <ArrowRight aria-hidden="true" className="size-4" />
          </Link>
        </Button>
      </section>
      <section aria-labelledby="workflow-heading">
        <div className="mb-4 flex items-center justify-between">
          <h2 id="workflow-heading" className="text-lg font-semibold">
            From source to signal
          </h2>
          <span className="text-xs text-muted-foreground">Coming next</span>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          {[
            {
              icon: Files,
              title: "Inspect markets",
              body: "Read original terms, resolution sources, and evidence.",
            },
            {
              icon: GitCompareArrows,
              title: "Compare contracts",
              body: "Understand settlement differences before trusting a match.",
            },
            {
              icon: ChartNoAxesCombined,
              title: "Evaluate opportunities",
              body: "Review depth, fees, freshness, and execution assumptions.",
            },
          ].map(({ icon: Icon, title, body }, i) => (
            <article
              key={title}
              className="rounded-lg border border-border bg-card p-6"
            >
              <div className="mb-6 flex items-center justify-between">
                <Icon aria-hidden="true" className="size-5 text-primary" />
                <span className="text-xs tabular-nums text-muted-foreground">
                  0{i + 1}
                </span>
              </div>
              <h3 className="font-semibold">{title}</h3>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                {body}
              </p>
            </article>
          ))}
        </div>
      </section>
      <EmptyState
        title="Evidence comes first"
        description="Similar titles do not establish equivalent settlement. Unverified matches and stale quotes must stay explicit; a quote-supported estimate never guarantees profit or a cross-exchange fill."
      />
    </div>
  );
}
