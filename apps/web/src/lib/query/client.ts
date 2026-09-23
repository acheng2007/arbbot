import { ApiError, failureFromStatus, type ApiFailure } from "@/lib/api/errors";
import { parseOrigin, ORIGIN_HEADER, type DataOrigin } from "@/lib/api/origin";
import { buildPath, type RequestArgs } from "@/lib/api/request";
import type { ApiOperations, OperationId } from "@/lib/api/schema";

/** Operations the browser may request through the same-origin proxy. */
export type BrowserOperation = Extract<
  OperationId,
  | "markets"
  | "market"
  | "extraction"
  | "book"
  | "marketVersion"
  | "snapshot"
  | "matches"
  | "opportunities"
  | "history"
  | "evaluations"
>;

export type ApiResult<K extends BrowserOperation> = {
  data: ApiOperations[K]["response"];
  /** Whether the payload came from the backend or from recorded fixtures. */
  origin: DataOrigin;
  /** When this browser received the payload, used for quote-age display. */
  receivedAt: number;
};

function failureOf(body: unknown, status: number): ApiFailure {
  if (
    body &&
    typeof body === "object" &&
    "failure" in body &&
    typeof body.failure === "string"
  )
    return body.failure as ApiFailure;
  return failureFromStatus(status);
}

/**
 * Calls the same-origin proxy so the backend URL never reaches the browser
 * bundle. Query and path values are flattened into the search string because
 * the proxy re-maps them using the generated parameter registry.
 */
export async function requestOperation<K extends BrowserOperation>(
  operation: K,
  args: RequestArgs<K> = {},
  signal?: AbortSignal,
): Promise<ApiResult<K>> {
  const search = buildPath<K>(
    "" as ApiOperations[K]["route"],
    { query: { ...args.params, ...args.query } } as RequestArgs<K>,
  );

  let response: Response;
  try {
    response = await fetch(`/api/data/${operation}${search}`, {
      cache: "no-store",
      headers: { accept: "application/json" },
      signal,
    });
  } catch {
    if (signal?.aborted) throw new ApiError("cancelled", "Request cancelled");
    throw new ApiError("unreachable", "The workspace API is unreachable");
  }

  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    const failure = failureOf(body, response.status);
    throw new ApiError(
      failure,
      `Request failed (${response.status})`,
      response.status,
    );
  }

  let data: ApiOperations[K]["response"];
  try {
    // Financial values arrive as JSON strings and stay strings; nothing is parsed
    // into a binary floating-point number anywhere on this path.
    data = (await response.json()) as ApiOperations[K]["response"];
  } catch {
    throw new ApiError(
      "invalid_response",
      "The workspace API returned malformed JSON",
    );
  }

  return {
    data,
    origin: parseOrigin(response.headers.get(ORIGIN_HEADER)),
    receivedAt: Date.now(),
  };
}
