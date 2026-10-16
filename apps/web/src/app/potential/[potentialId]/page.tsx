import { PotentialDetail } from "@/features/opportunities/potential-detail";

export default async function PotentialPage({
  params,
}: {
  params: Promise<{ potentialId: string }>;
}) {
  const { potentialId } = await params;
  return <PotentialDetail id={potentialId} />;
}
