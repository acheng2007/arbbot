import type { Comparison, ContractDefinition } from "@/lib/api/schema";
import { DifferenceStatusBadge, fieldLabel } from "@/features/shared/status";
import { SourceQuote } from "./source-terms";

const SOURCE_LABEL = {
  title: "market title",
  rules: "published rules",
  settlement_details: "settlement details",
} as const;

function Evidence({
  definition,
  field,
}: {
  definition: ContractDefinition | null;
  field: string;
}) {
  const fact = definition?.facts[field as keyof ContractDefinition["facts"]];
  if (!fact)
    return (
      <p className="text-sm text-muted-foreground italic">
        Not extracted from this contract.
      </p>
    );
  return (
    <div>
      <p className="text-sm font-medium">{fact.value}</p>
      <p className="mt-1.5 text-xs text-muted-foreground">
        Quoted from the {SOURCE_LABEL[fact.source]}
        {fact.source_key ? ` (${fact.source_key})` : ""}
      </p>
      <div className="mt-1.5">
        <SourceQuote>{fact.quote}</SourceQuote>
      </div>
    </div>
  );
}

/**
 * Every compared field is listed with the exact source quotation behind each
 * side, so a reader can check the evidence rather than trust the verdict.
 */
export function DifferenceTable({
  comparison,
  leftLabel = "Left contract",
  rightLabel = "Right contract",
}: {
  comparison: Comparison;
  leftLabel?: string;
  rightLabel?: string;
}) {
  const unresolved = comparison.differences.filter(
    (difference) => difference.status !== "equal",
  );

  return (
    <div className="space-y-4">
      <p className="text-sm leading-6 text-muted-foreground">
        {unresolved.length === 0
          ? "Every compared settlement field agrees across both contracts."
          : `${unresolved.length} of ${comparison.differences.length} compared fields differ or could not be determined. Unresolved fields are listed first.`}
      </p>
      <ul className="space-y-3">
        {[...comparison.differences]
          .sort(
            (a, b) =>
              Number(a.status === "equal") - Number(b.status === "equal"),
          )
          .map((difference) => (
            <li
              key={difference.field}
              className="rounded-lg border border-border bg-card p-4 sm:p-5"
              data-field={difference.field}
              data-status={difference.status}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h4 className="font-semibold">
                  {fieldLabel(difference.field)}
                </h4>
                <DifferenceStatusBadge status={difference.status} />
              </div>
              <div className="mt-4 grid gap-5 md:grid-cols-2">
                {[
                  { label: leftLabel, definition: comparison.left },
                  { label: rightLabel, definition: comparison.right },
                ].map(({ label, definition }) => (
                  <div key={label}>
                    <p className="mb-1.5 text-xs font-semibold tracking-wider text-muted-foreground uppercase">
                      {label}
                    </p>
                    <Evidence
                      definition={definition}
                      field={difference.field}
                    />
                  </div>
                ))}
              </div>
            </li>
          ))}
      </ul>
    </div>
  );
}
