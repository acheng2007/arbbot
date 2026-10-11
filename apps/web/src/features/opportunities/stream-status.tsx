"use client";
import { Radio, Unplug } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { describeAge, useNow } from "@/components/freshness";
import type { StreamState } from "./use-stream";

/**
 * Reports the live connection honestly. While the stream is down the interface
 * states that the figures are no longer being confirmed, so a successful render
 * from a previous update cannot be mistaken for a current one.
 */
export function StreamStatusBanner({ state }: { state: StreamState }) {
  const now = useNow();
  const confirmedAgo =
    now !== null && state.lastEventAt !== null
      ? describeAge((now - state.lastEventAt) / 1000)
      : null;

  if (state.status === "open")
    return (
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="positive">
          <Radio aria-hidden="true" className="size-3" />
          Live updates connected
        </Badge>
        {confirmedAgo && (
          <span className="text-xs text-muted-foreground">
            Last snapshot {confirmedAgo}. Quote freshness is shown separately.
          </span>
        )}
      </div>
    );

  return (
    <div
      role="status"
      className="flex items-start gap-3 rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm leading-6 text-amber-950"
    >
      <Unplug aria-hidden="true" className="mt-1 size-4 shrink-0" />
      <p>
        <span className="font-semibold">
          {state.status === "connecting"
            ? "Connecting to live updates."
            : "Live updates disconnected, retrying."}
        </span>{" "}
        {confirmedAgo
          ? `The last snapshot arrived ${confirmedAgo}. Quotes may no longer hold.`
          : "No snapshot has arrived yet. Quote freshness is shown separately."}
        {state.drops > 0 &&
          ` The connection has dropped ${state.drops} ${state.drops === 1 ? "time" : "times"} since this page loaded.`}
      </p>
    </div>
  );
}
