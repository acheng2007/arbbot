import { Database, FlaskConical } from "lucide-react";
import type { DataOrigin } from "@/lib/api/origin";
import { Badge } from "@/components/ui/badge";

/**
 * Recorded fixtures must never read as live exchange data, so the banner states
 * the origin in full rather than relying on a small badge alone.
 */
export function OriginBanner({ origin }: { origin: DataOrigin }) {
  if (origin === "backend") return null;
  return (
    <details className="rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-xs text-sky-950">
      <summary className="cursor-pointer font-medium">
        {origin === "recorded_backend"
          ? "Offline recorded acceptance data"
          : "Recorded fixture data"}{" "}
        · Not tradable
      </summary>
      <p className="mt-2 leading-5">
        Recorded prices, matches, and estimates are for development.{" "}
        {origin === "fixtures"
          ? "No exchange or backend was contacted."
          : "The backend uses recorded exchange responses."}{" "}
        Synthetic scenarios are labeled explicitly.
      </p>
    </details>
  );
}

export function OriginBadge({ origin }: { origin: DataOrigin }) {
  return origin === "fixtures" ? (
    <Badge tone="info">
      <FlaskConical aria-hidden="true" className="size-3" />
      Fixture data
    </Badge>
  ) : (
    <Badge tone="neutral">
      <Database aria-hidden="true" className="size-3" />
      Backend data
    </Badge>
  );
}

/** The backend's own ingestion mode, which is independent of the data origin. */
export function ModeBadge({
  mode,
  feedOrigin,
}: {
  mode: "simulation" | "live";
  feedOrigin?: "exchange" | "synthetic_recording" | "recorded_exchange";
}) {
  if (feedOrigin && feedOrigin !== "exchange")
    return (
      <Badge tone="caution">
        {feedOrigin === "synthetic_recording"
          ? "Synthetic recording"
          : "Recorded exchange"}
      </Badge>
    );
  return (
    <Badge tone={mode === "live" ? "positive" : "caution"}>
      {mode === "live" ? "Live feed" : "Simulation"}
    </Badge>
  );
}
