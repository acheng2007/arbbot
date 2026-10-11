"use client";
import { useMemo } from "react";
import { useQueries } from "@tanstack/react-query";
import { requestOperation } from "@/lib/query/client";
import { queryKey } from "@/lib/query/keys";
import { useApi } from "@/lib/query/hooks";
import type { Market } from "@/lib/api/schema";

/**
 * Markets indexed by id so match and opportunity screens can name the contracts
 * they reference. Shared through the query cache, so it costs one request.
 */
export function useMarketIndex(requiredIds?: string[]) {
  const query = useApi(
    "markets",
    { query: { limit: 200 } },
    { enabled: requiredIds === undefined },
  );
  const referenced = useQueries({
    queries: [...new Set(requiredIds ?? [])].map((id) => ({
      queryKey: queryKey("market", { params: { market_id: id } }),
      queryFn: ({ signal }: { signal: AbortSignal }) =>
        requestOperation("market", { params: { market_id: id } }, signal),
    })),
  });
  const index = useMemo(() => {
    const map = new Map<string, Market>();
    for (const market of query.data?.data ?? []) map.set(market.id, market);
    for (const result of referenced)
      if (result.data) map.set(result.data.data.id, result.data.data);
    return map;
  }, [query.data, referenced]);
  return { ...query, index };
}
