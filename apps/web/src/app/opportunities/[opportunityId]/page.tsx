import type { Metadata } from "next";
import { routeParam } from "@/lib/routing";
import { OpportunityDetail } from "@/features/opportunities/opportunity-detail";

export const metadata: Metadata = {
  title: "Opportunity detail",
  description:
    "Full cost breakdown, legs, payout scenarios, assumptions, and the review behind one opportunity.",
};

export default async function OpportunityPage({
  params,
}: PageProps<"/opportunities/[opportunityId]">) {
  const { opportunityId } = await params;
  return <OpportunityDetail opportunityId={routeParam(opportunityId)} />;
}
