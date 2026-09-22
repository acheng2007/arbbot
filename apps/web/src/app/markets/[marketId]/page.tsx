import type { Metadata } from "next";
import { routeParam } from "@/lib/routing";
import { MarketDetail } from "@/features/markets/market-detail";

export const metadata: Metadata = {
  title: "Market source detail",
  description:
    "Original venue terms, extracted settlement facts, and current quote health for one market.",
};

export default async function MarketPage({
  params,
}: PageProps<"/markets/[marketId]">) {
  const { marketId } = await params;
  return <MarketDetail marketId={routeParam(marketId)} />;
}
