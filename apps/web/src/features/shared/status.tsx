import { Badge, type BadgeTone } from "@/components/ui/badge";
import type { Comparison, Difference, Match } from "@/lib/api/schema";

/**
 * Verification provenance distinguishes automatic rules from historical review.
 * Similarity remains a discovery signal.
 */
const MATCH_STATUS: Record<
  Match["status"],
  { tone: BadgeTone; label: string }
> = {
  candidate: { tone: "caution", label: "Unverified match" },
  verified: { tone: "positive", label: "Verified in review" },
  rejected: { tone: "critical", label: "Rejected in review" },
};

export function MatchStatusBadge({
  status,
  qualification,
  relationship,
  operatorVeto,
  historical,
}: {
  status: Match["status"];
  qualification?: Match["qualification"];
  relationship?: Match["relationship"];
  operatorVeto?: boolean;
  historical?: boolean;
}) {
  if (historical) return <Badge tone="neutral">Historical comparison</Badge>;
  if (operatorVeto) return <Badge tone="critical">Operator veto</Badge>;
  if (
    relationship === "mismatch" ||
    (qualification?.status === "incompatible" &&
      !qualification.blocked_reasons?.includes("explicit_operator_veto"))
  )
    return <Badge tone="critical">Mismatch</Badge>;
  if (status === "verified" && qualification?.basis === "automatic_rules") {
    return <Badge tone="positive">Verified automatically</Badge>;
  }
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

export function reasonLabel(reason: string): string {
  for (const side of ["left", "right"]) {
    if (reason.startsWith(`${side}:`))
      return `${fieldLabel(side)} contract: ${reasonLabel(reason.slice(side.length + 1))}`;
  }
  if (reason.startsWith("unmodeled_policy:"))
    return `The settlement verifier cannot yet interpret ${reason.split(":")[1].replaceAll("_", " ")} rules.`;
  const known: Record<string, string> = {
    source_evidence_incomplete: "Required source evidence is incomplete.",
    definition_schema_upgrade_required:
      "These terms require a newer supported settlement interpretation.",
    applicable_document_language_unmodeled:
      "The settlement verifier cannot yet interpret the applicable document language.",
    applicable_sources_incomplete:
      "Required settlement documents have not all been captured.",
    applicable_document_missing:
      "An applicable settlement document is missing.",
    instrument_document_relationship_missing:
      "Documents have not been linked to this exact instrument.",
    product_specification_applicability_unverified:
      "The product specification has not been linked to this instrument.",
    clarification_applicability_unverified:
      "Applicable amendments and clarifications have not been established.",
    unsupported_contract_family:
      "The settlement verifier cannot yet interpret these rules.",
    public_costs_unavailable:
      "Current public fees or financial constraints are unavailable.",
    explicit_operator_veto:
      "An operator has blocked publication for this relationship.",
    document_unavailable_or_stale:
      "A required source document is unavailable or stale.",
    qualification_pending: "Automatic settlement checks are pending.",
  };
  if (known[reason]) return known[reason];
  if (reason.startsWith("contract_field_unknown:"))
    return `${fieldLabel(reason.split(":")[1])} is not established for both contracts.`;
  if (reason.startsWith("contract_field_different:"))
    return `${fieldLabel(reason.split(":")[1])} differs between the contracts.`;
  return fieldLabel(reason);
}

const VENUE_LABEL: Record<string, string> = {
  kalshi: "Kalshi",
  polymarket: "Polymarket International",
  polymarket_us: "Polymarket US",
};

export function venueLabel(venue: string) {
  return VENUE_LABEL[venue] ?? venue;
}
