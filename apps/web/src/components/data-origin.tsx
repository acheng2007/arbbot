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
    <div
      role="status"
      className="flex items-start gap-3 rounded-lg border border-sky-300 bg-sky-50 p-4 text-sm text-sky-950"
    >
      <FlaskConical aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
      {origin === "recorded_backend" ? <p className="leading-6">
        <strong>Offline recorded acceptance data.</strong> The backend and persistent worker use recorded exchange responses.
        Synthetic scenarios are labeled explicitly and are not tradable.
      </p> : <p className="leading-6">
        <span className="font-semibold">Recorded fixture data.</span> No
        exchange or backend was contacted. Prices, matches, and profit figures
        on this page are illustrative recordings for development and are not
        tradable.
      </p>}
    </div>
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
export function ModeBadge({ mode, feedOrigin }: { mode: "simulation" | "live";
  feedOrigin?: "exchange" | "synthetic_recording" | "recorded_exchange" }) {
  if (feedOrigin && feedOrigin !== "exchange") return <Badge tone="caution">
    {feedOrigin === "synthetic_recording" ? "Synthetic recording" : "Recorded exchange"}
  </Badge>;
  return (
    <Badge tone={mode === "live" ? "positive" : "caution"}>
      {mode === "live" ? "Live feed" : "Simulation"}
    </Badge>
  );
}
