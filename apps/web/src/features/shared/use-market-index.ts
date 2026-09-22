"use client";
import { useMemo } from "react";
import { useApi } from "@/lib/query/hooks";
import type { Market } from "@/lib/api/schema";

/**
 * Markets indexed by id so match and opportunity screens can name the contracts
 * they reference. Shared through the query cache, so it costs one request.
 */
export function useMarketIndex() {
  const query = useApi("markets", { query: { limit: 200 } });
  const index = useMemo(() => {
    const map = new Map<string, Market>();
    for (const market of query.data?.data ?? []) map.set(market.id, market);
    return map;
  }, [query.data]);
  return { ...query, index };
}
