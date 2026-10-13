"use client";
import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

export type StreamStatus = "connecting" | "open" | "reconnecting";

export type StreamState = {
  status: StreamStatus;
  /** When the stream last delivered a snapshot; quote freshness is independent. */
  lastEventAt: number | null;
  /** How many times the connection has dropped since the page loaded. */
  drops: number;
};

/**
 * Subscribes to backend updates and refreshes the opportunity queries when the
 * server signals a change.
 *
 * The browser's own EventSource reconnection is used rather than a bespoke one.
 * A dropped connection never leaves the screen claiming to be current: the
 * status and the age of the last confirmed event are reported to the caller so
 * the interface can mark the data as unverified.
 */
export function useOpportunityStream(enabled = true) {
  const client = useQueryClient();
  const [state, setState] = useState<StreamState>({
    status: "connecting",
    lastEventAt: null,
    drops: 0,
  });
  const openedOnce = useRef(false);

  useEffect(() => {
    if (!enabled || typeof EventSource === "undefined") return;
    const source = new EventSource("/api/stream");

    const markCurrent = () =>
      setState((previous) => ({
        ...previous,
        status: "open",
        lastEventAt: Date.now(),
      }));

    source.addEventListener("snapshot", () => {
      markCurrent();
      // Let pending reads finish when snapshots arrive faster than the API.
      // Repeated cancellation can prevent refreshed data from reaching the UI.
      void client.invalidateQueries({ queryKey: ["arbbot", "opportunities"] }, { cancelRefetch: false });
      void client.invalidateQueries({ queryKey: ["arbbot", "evaluations"] }, { cancelRefetch: false });
      void client.invalidateQueries({ queryKey: ["arbbot", "history"] }, { cancelRefetch: false });
      for (const operation of ["opportunity", "accessSummary", "markets", "marketSummaries", "market", "matches", "match", "book", "status"])
        void client.invalidateQueries({ queryKey: ["arbbot", operation] }, { cancelRefetch: false });
    });

    source.onopen = () => {
      openedOnce.current = true;
      setState((previous) => ({ ...previous, status: "open" }));
    };

    source.onerror = () => {
      setState((previous) => ({
        status: "reconnecting",
        lastEventAt: previous.lastEventAt,
        drops: previous.drops + (openedOnce.current ? 1 : 0),
      }));
      openedOnce.current = false;
    };

    return () => source.close();
  }, [client, enabled]);

  return state;
}
