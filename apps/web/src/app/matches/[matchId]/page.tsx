import type { Metadata } from "next";
import { routeParam } from "@/lib/routing";
import { ComparisonDetail } from "@/features/comparisons/comparison-detail";

export const metadata: Metadata = {
  title: "Contract comparison",
  description:
    "Side-by-side settlement terms, source quotations, and the recorded review for one proposed pair.",
};

export default async function MatchPage({
  params,
}: PageProps<"/matches/[matchId]">) {
  const { matchId } = await params;
  return <ComparisonDetail matchId={routeParam(matchId)} />;
}
