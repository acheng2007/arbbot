import type { RequestArgs } from "@/lib/api/request";
import type { BrowserOperation } from "./client";

/**
 * Every cache key is derived from the operation and its arguments, so two
 * screens requesting the same data share one cache entry and one request.
 */
export function queryKey<K extends BrowserOperation>(
  operation: K,
  args: RequestArgs<K> = {},
) {
  const normalize = (values: Record<string, unknown> | undefined) =>
    Object.fromEntries(
      Object.entries(values ?? {})
        .filter(
          ([, value]) => value !== undefined && value !== null && value !== "",
        )
        .sort(([a], [b]) => a.localeCompare(b)),
    );

  return [
    "arbbot",
    operation,
    normalize(args.params as Record<string, unknown> | undefined),
    normalize(args.query as Record<string, unknown> | undefined),
  ] as const;
}
