"use client";
import { useState, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";
/** Mount optional evidence only after it is requested; preserve it on subsequent toggles. */
export function Disclosure({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  const [visited, setVisited] = useState(false);
  return (
    <details
      className="group rounded-xl border border-border bg-card"
      onToggle={(event) => {
        if (event.currentTarget.open) setVisited(true);
      }}
    >
      <summary className="flex cursor-pointer list-none items-center justify-between gap-4 p-4 text-sm font-semibold sm:p-5">
        {title}
        <ChevronDown
          aria-hidden="true"
          className="size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180"
        />
      </summary>
      {visited && (
        <div className="border-t border-border p-4 sm:p-5">{children}</div>
      )}
    </details>
  );
}
