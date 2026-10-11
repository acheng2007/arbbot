import { Badge, type BadgeTone } from "@/components/ui/badge";
import type { Comparison, Difference, Match } from "@/lib/api/schema";

/**
 * A match status always reflects a recorded human review. Similarity is a
 * discovery signal only and never appears as a verification state.
 */
const MATCH_STATUS: Record<
  Match["status"],
  { tone: BadgeTone; label: string }
> = {
  candidate: { tone: "caution", label: "Candidate, not verified" },
  verified: { tone: "positive", label: "Verified in review" },
  rejected: { tone: "critical", label: "Rejected in review" },
};

export function MatchStatusBadge({ status }: { status: Match["status"] }) {
  const { tone, label } = MATCH_STATUS[status];
  return <Badge tone={tone}>{label}</Badge>;
}

const COMPARISON_STATUS: Record<
  Comparison["status"],
  { tone: BadgeTone; label: string }
> = {
  compatible: { tone: "positive", label: "Terms compatible" },
  conflict: { tone: "critical", label: "Terms conflict" },
  incomplete: { tone: "caution", label: "Terms incomplete" },
};

export function ComparisonStatusBadge({
  status,
}: {
  status: Comparison["status"];
}) {
  const { tone, label } = COMPARISON_STATUS[status];
  return <Badge tone={tone}>{label}</Badge>;
}

const DIFFERENCE_STATUS: Record<
  Difference["status"],
  { tone: BadgeTone; label: string }
> = {
  equal: { tone: "positive", label: "Same" },
  different: { tone: "critical", label: "Differs" },
  unknown: { tone: "caution", label: "Unknown" },
};

export function DifferenceStatusBadge({
  status,
}: {
  status: Difference["status"];
}) {
  const { tone, label } = DIFFERENCE_STATUS[status];
  return <Badge tone={tone}>{label}</Badge>;
}

/** Turns `reference_period` into `Reference period` for display. */
export function fieldLabel(field: string) {
  const spaced = field.replace(/_/g, " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

const VENUE_LABEL: Record<string, string> = {
  kalshi: "Kalshi",
  polymarket: "Polymarket International",
  polymarket_us: "Polymarket US",
};

export function venueLabel(venue: string) {
  return VENUE_LABEL[venue] ?? venue;
}
