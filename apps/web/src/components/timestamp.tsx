"use client";
import { useSyncExternalStore } from "react";

// Explicit components rather than dateStyle/timeStyle, which cannot be combined
// with timeZoneName. The zone matters: settlement deadlines turn on it.
const FORMAT = new Intl.DateTimeFormat(undefined, {
  year: "numeric",
  month: "short",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  timeZoneName: "short",
});

// The server has no way to know the reader's time zone, so the exact instant is
// rendered on the server and replaced with local time once hydrated.
const noop = () => () => {};

function useHydrated() {
  return useSyncExternalStore(
    noop,
    () => true,
    () => false,
  );
}

/**
 * Renders an instant in the reader's own time zone. Settlement deadlines turn
 * on time zones, so the machine-readable value is kept in the `dateTime`
 * attribute and the zone is always shown.
 */
export function Timestamp({ value }: { value: string }) {
  const hydrated = useHydrated();
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed))
    return <span className="font-mono text-xs">{value}</span>;
  return (
    <time dateTime={value} title={value}>
      {hydrated ? FORMAT.format(parsed) : value}
    </time>
  );
}
