"use client";
import { useSyncExternalStore } from "react";
import { Badge, type BadgeTone } from "@/components/ui/badge";

/**
 * The backend treats quotes older than 30 seconds as unusable, so the interface
 * uses the same boundary rather than inventing a friendlier one.
 */
export const QUOTE_WINDOW_SECONDS = 30;
const SEVERE_SECONDS = 300;

// One shared clock for every age and countdown on the page, so a screen with
// many timestamps still re-renders once per second rather than once per widget.
let clockNow = Date.now();
const clockListeners = new Set<() => void>();
let clockTimer: ReturnType<typeof setInterval> | null = null;

function subscribeToClock(listener: () => void) {
  clockListeners.add(listener);
  clockTimer ??= setInterval(() => {
    clockNow = Date.now();
    for (const notify of clockListeners) notify();
  }, 1000);

  return () => {
    clockListeners.delete(listener);
    if (clockListeners.size === 0 && clockTimer) {
      clearInterval(clockTimer);
      clockTimer = null;
    }
  };
}

/**
 * Current time, ticking once a second. Returns null on the server and during
 * hydration, because an age rendered on the server is wrong by the time it
 * reaches the browser.
 */
export function useNow() {
  return useSyncExternalStore(
    subscribeToClock,
    () => clockNow,
    () => null,
  );
}

export function describeAge(seconds: number) {
  if (seconds < 0) return "in the future";
  if (seconds < 60) return `${Math.floor(seconds)}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86_400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86_400)}d ago`;
}

export function freshnessTone(seconds: number): BadgeTone {
  if (seconds > SEVERE_SECONDS) return "critical";
  if (seconds > QUOTE_WINDOW_SECONDS) return "caution";
  return "positive";
}

/** Age of a single timestamp, where no source-versus-receipt distinction exists. */
export function Age({ at, label }: { at: string; label: string }) {
  const now = useNow();
  const parsed = Date.parse(at);
  if (Number.isNaN(parsed))
    return <Badge tone="critical">{label} timestamp unreadable</Badge>;
  if (now === null) return <Badge tone="neutral">{label} age loading</Badge>;
  const seconds = (now - parsed) / 1000;
  return (
    <Badge tone={freshnessTone(seconds)} title={at}>
      {label} {describeAge(seconds)}
    </Badge>
  );
}

type Props = {
  /** Exchange-supplied timestamp, when the venue provides one. */
  sourceAt?: string | null;
  /** When this system received the data. Always available. */
  receivedAt: string;
  label?: string;
};

/**
 * Shows quote age against the source timestamp when the venue supplies one and
 * falls back to the receipt timestamp otherwise, saying which was used. The two
 * are never conflated, because a missing source timestamp hides real latency.
 */
export function QuoteAge({ sourceAt, receivedAt, label = "Quote" }: Props) {
  const now = useNow();
  const basis = sourceAt ?? receivedAt;
  const parsed = Date.parse(basis);

  if (Number.isNaN(parsed))
    return <Badge tone="critical">{label} timestamp unreadable</Badge>;

  if (now === null)
    return (
      <Badge tone="neutral">
        <span className="sr-only">{label} age</span>
        Measuring age
      </Badge>
    );

  const seconds = (now - parsed) / 1000;
  const tone = seconds < 0 ? "critical" : freshnessTone(seconds);
  const source = sourceAt ? "exchange timestamp" : "receipt time only";

  return (
    <Badge tone={tone} title={`${new Date(parsed).toISOString()} (${source})`}>
      {seconds > QUOTE_WINDOW_SECONDS ? `Stale ${label.toLowerCase()}` : label}{" "}
      {describeAge(seconds)}
      <span className="font-normal opacity-80">({source})</span>
    </Badge>
  );
}

/** Counts down to an expiry instant and states plainly once it has passed. */
export function ValidUntil({ validUntil }: { validUntil: string }) {
  const now = useNow();
  const parsed = Date.parse(validUntil);
  if (Number.isNaN(parsed))
    return <Badge tone="critical">Expiry unreadable</Badge>;
  if (now === null) return <Badge tone="neutral">Checking validity</Badge>;

  const seconds = (parsed - now) / 1000;
  if (seconds <= 0)
    return <Badge tone="critical">Expired {describeAge(-seconds)}</Badge>;
  return (
    <Badge tone={seconds < 10 ? "caution" : "positive"}>
      Valid for {Math.floor(seconds)}s
    </Badge>
  );
}
