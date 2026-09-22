import type { Metadata } from "next";
import { OpportunityDashboard } from "@/features/opportunities/dashboard";

export const metadata: Metadata = {
  title: "Opportunities",
  description:
    "Quote-supported arbitrage estimates with costs, payout scenarios, freshness, and execution assumptions.",
};

export default function OpportunitiesPage() {
  return (
    <div className="space-y-7">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
          Opportunities
        </h1>
        <p className="mt-3 max-w-2xl text-base leading-7 text-muted-foreground">
          Verified contract pairs whose current executable quotes support a
          positive net result after fees, depth costs, and slippage allowance.
        </p>
      </header>
      <OpportunityDashboard />
    </div>
  );
}
