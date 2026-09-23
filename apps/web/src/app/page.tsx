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
              Start here
            </span>
            <h2 className="mt-3 text-xl font-semibold">
              Opportunities, with their evidence attached
            </h2>
            <p className="mt-2 max-w-xl text-sm leading-6 text-muted-foreground">
              Every estimate links back to the contract comparison and the
              source terms it rests on. Nothing on this site places an order.
            </p>
          </div>
        </div>
        <div className="mt-6 flex flex-wrap gap-3">
          <Button asChild>
            <Link href="/opportunities">
              View opportunities
              <ArrowRight aria-hidden="true" className="size-4" />
            </Link>
          </Button>
          <Button asChild variant="outline">
            <Link href="/connection">Check API connection</Link>
          </Button>
        </div>
      </section>
      <section aria-labelledby="workflow-heading">
        <h2 id="workflow-heading" className="mb-4 text-lg font-semibold">
          From source to signal
        </h2>
        <div className="grid gap-4 md:grid-cols-3">
          {[
            {
              icon: Files,
              href: "/markets",
              title: "Inspect markets",
              body: "Read original terms, resolution sources, and quote health.",
            },
            {
              icon: GitCompareArrows,
              href: "/matches",
              title: "Compare contracts",
              body: "Understand settlement differences before trusting a match.",
            },
            {
              icon: ChartNoAxesCombined,
              href: "/opportunities",
              title: "Evaluate opportunities",
              body: "Review depth, fees, freshness, and execution assumptions.",
            },
          ].map(({ icon: Icon, href, title, body }, i) => (
            <article key={title}>
              <Link
                href={href}
                className="block h-full rounded-lg border border-border bg-card p-6 transition-colors hover:border-ring focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
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
              </Link>
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
