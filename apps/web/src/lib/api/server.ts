import "server-only";
import { backendUrl } from "@/lib/backend";
import { ApiError, failureFromStatus } from "./errors";
import type { DataOrigin } from "./origin";
import { buildPath, type RequestArgs } from "./request";
import {
  API_OPERATIONS,
  type ApiOperations,
  type ReadOperationId as OperationId,
} from "./schema";
import { recordedDataset } from "./fixtures";

/**
 * Fixture data is opt-in. An unset or misspelled value always reads the real
 * backend so recorded data can never stand in for live data by accident.
 */
export function dataOrigin(): DataOrigin {
  return process.env.ARBBOT_WEB_DATA_SOURCE === "fixtures"
    ? "fixtures"
    : "backend";
}

const TIMEOUT_MS = 8000;

async function fromBackend<K extends OperationId>(
  operation: K,
  args: RequestArgs<K>,
  signal?: AbortSignal,
): Promise<ApiOperations[K]["response"]> {
  const path = buildPath<K>(
    API_OPERATIONS[operation].route as ApiOperations[K]["route"],
    args,
  );
  const timeout = AbortSignal.timeout(TIMEOUT_MS);
  const combined = signal ? AbortSignal.any([signal, timeout]) : timeout;

  let response: Response;
  try {
    response = await fetch(`${backendUrl()}${path}`, {
      cache: "no-store",
      headers: { accept: "application/json" },
      signal: combined,
    });
  } catch {
    if (signal?.aborted) throw new ApiError("cancelled", "Request cancelled");
    if (timeout.aborted) throw new ApiError("timeout", "Backend timed out");
    throw new ApiError("unreachable", "Backend unreachable");
  }

  if (!response.ok)
    throw new ApiError(
      failureFromStatus(response.status),
      `Backend responded ${response.status}`,
      response.status,
    );

  try {
    // Financial values arrive as JSON strings and stay strings through parsing.
    return (await response.json()) as ApiOperations[K]["response"];
  } catch {
    throw new ApiError("invalid_response", "Backend returned malformed JSON");
  }
}

// Pagination values arrive as query strings; these are counts, not money, so
// numeric coercion is safe here.
function paginate<T>(items: T[], query?: { limit?: number; offset?: number }) {
  const offset = Math.max(0, Number(query?.offset ?? 0) || 0);
  const limit = Math.min(200, Math.max(1, Number(query?.limit ?? 100) || 100));
  return items.slice(offset, offset + limit);
}

function required<T>(value: T | undefined, what: string): T {
  if (value === undefined)
    throw new ApiError("not_found", `${what} not found`, 404);
  return value;
}

// Returns `unknown` because TypeScript cannot narrow the generic response type
// through a switch; `readOperation` restores the typed result for callers.
function fromFixtures(
  operation: OperationId,
  args: RequestArgs<OperationId>,
): unknown {
  const params = (args.params ?? {}) as Record<string, string>;
  const query = (args.query ?? {}) as {
    limit?: number;
    offset?: number;
    venue?: string | null;
    market_id?: string | null;
  };
  const fixtures = recordedDataset();

  switch (operation) {
    case "liveness":
    case "readiness":
      return { status: "ok", mode: "simulation" };
    case "status":
      return { mode: "simulation", venues: ["kalshi", "polymarket"] };
    case "venues":
      return [
        {
          id: "kalshi",
          name: "Kalshi",
          enabled: true,
          evaluation_enabled: true,
          access_note: "Simulation",
        },
        {
          id: "polymarket",
          name: "Polymarket International",
          enabled: true,
          evaluation_enabled: true,
          access_note: "Simulation",
        },
      ];
    case "markets": {
      const venue = query.venue;
      const filtered = venue
        ? fixtures.markets.filter((market) => market.venue === venue)
        : fixtures.markets;
      return paginate(filtered, query);
    }
    case "market":
      return required(
        fixtures.markets.find((market) => market.id === params.market_id),
        "Market",
      );
    case "marketVersion": {
      const market = required(
        fixtures.markets.find((entry) => entry.id === params.market_id),
        "Market",
      );
      if (market.terms_hash !== params.terms_hash)
        throw new ApiError("not_found", "Market version not found", 404);
      return market;
    }
    case "extraction":
      return required(fixtures.extractions[params.market_id], "Extraction");
    case "book":
      return required(fixtures.books[params.market_id], "Book");
    case "snapshot":
      return required(
        Object.values(fixtures.books).find(
          (book) => book.market_id === params.snapshot_id,
        ),
        "Snapshot",
      );
    case "match":
      return required(
        fixtures.matches.find((entry) => entry.id === params.match_id),
        "Match",
      );
    case "matches":
      return paginate(
        fixtures.matches.filter(
          (entry) =>
            !query.market_id ||
            entry.left_id === query.market_id ||
            entry.right_id === query.market_id,
        ),
        query,
      );
    case "opportunities":
      return paginate(fixtures.opportunities, query);
    case "history":
      return paginate(fixtures.history, query);
    case "evaluations":
      return paginate(fixtures.evaluations, query);
    default:
      throw new ApiError(
        "invalid_request",
        `Operation ${operation} has no fixture recording`,
      );
  }
}

/** Reads one operation from the configured source. Server-side only. */
export async function readOperation<K extends OperationId>(
  operation: K,
  args: RequestArgs<K> = {},
  signal?: AbortSignal,
): Promise<{ origin: DataOrigin; data: ApiOperations[K]["response"] }> {
  const origin = dataOrigin();
  if (origin === "fixtures")
    return {
      origin,
      data: fromFixtures(
        operation,
        args as RequestArgs<OperationId>,
      ) as ApiOperations[K]["response"],
    };
  return { origin, data: await fromBackend(operation, args, signal) };
}
