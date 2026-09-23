"use client";
import { useQuery, type UseQueryOptions } from "@tanstack/react-query";
import { ApiError } from "@/lib/api/errors";
import type { RequestArgs } from "@/lib/api/request";
import {
  requestOperation,
  type ApiResult,
  type BrowserOperation,
} from "./client";
import { queryKey } from "./keys";

type Options<K extends BrowserOperation> = Omit<
  UseQueryOptions<
    ApiResult<K>,
    ApiError,
    ApiResult<K>,
    ReturnType<typeof queryKey<K>>
  >,
  "queryKey" | "queryFn"
>;

/**
 * Reads one API operation. TanStack Query supplies the abort signal, so a
 * superseded request (a changed filter, an unmounted screen) is cancelled
 * rather than left to resolve into a stale render.
 */
export function useApi<K extends BrowserOperation>(
  operation: K,
  args: RequestArgs<K> = {},
  options: Options<K> = {},
) {
  return useQuery({
    queryKey: queryKey(operation, args),
    queryFn: ({ signal }) => requestOperation(operation, args, signal),
    // Cancelling a superseded request is the point; retrying one is not.
    retry: (count, error) =>
      count < 1 &&
      error.failure !== "cancelled" &&
      error.failure !== "not_found",
    ...options,
  });
}
