import { Suspense } from "react";
import { LoadingState } from "@/components/states";
import type { Metadata } from "next";
import { OpportunityDashboard } from "@/features/opportunities/dashboard";

export const metadata: Metadata = {
  title: "Opportunities",
  description:
    "Quote-supported arbitrage estimates with costs, payout scenarios, freshness, and execution assumptions.",
};

export default function OpportunitiesPage() {
  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
          Opportunities
        </h1>
      </header>
      <Suspense fallback={<LoadingState label="Loading opportunities" />}>
        <OpportunityDashboard />
      </Suspense>
    </div>
  );
}
