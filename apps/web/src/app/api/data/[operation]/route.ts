import type { NextRequest } from "next/server";
import { ApiError } from "@/lib/api/errors";
import { ORIGIN_HEADER } from "@/lib/api/origin";
import { readOperation } from "@/lib/api/server";
import { API_OPERATIONS, type OperationId } from "@/lib/api/schema";

// Read-only operations the browser may request. Streaming and health checks are
// excluded: the stream has its own route and health is served by /api/connection.
const EXPOSED = [
  "venues",
  "markets",
  "market",
  "extraction",
  "book",
  "marketVersion",
  "snapshot",
  "matches",
  "opportunities",
  "history",
  "evaluations",
] as const satisfies readonly OperationId[];

type Exposed = (typeof EXPOSED)[number];

function isExposed(value: string): value is Exposed {
  return (EXPOSED as readonly string[]).includes(value);
}

const STATUS: Record<ApiError["failure"], number> = {
  unreachable: 503,
  timeout: 504,
  cancelled: 499,
  not_found: 404,
  invalid_request: 400,
  backend_error: 502,
  invalid_response: 502,
};

export async function GET(
  request: NextRequest,
  context: RouteContext<"/api/data/[operation]">,
) {
  const { operation } = await context.params;
  if (!isExposed(operation))
    return Response.json(
      { failure: "not_found" },
      { status: 404, headers: { "Cache-Control": "no-store" } },
    );

  const definition = API_OPERATIONS[operation];
  const search = request.nextUrl.searchParams;
  const pick = (names: readonly string[]) =>
    Object.fromEntries(
      names
        .map((name) => [name, search.get(name)] as const)
        .filter(([, value]) => value !== null),
    );

  try {
    const { origin, data } = await readOperation(
      operation,
      {
        params: pick(definition.params),
        query: pick(definition.query),
        // The registry types params and query per operation; the values here are
        // validated strings drawn from the same registry.
      } as never,
      request.signal,
    );
    return Response.json(data, {
      headers: { "Cache-Control": "no-store", [ORIGIN_HEADER]: origin },
    });
  } catch (error) {
    if (error instanceof ApiError)
      return Response.json(
        { failure: error.failure },
        {
          status: STATUS[error.failure],
          headers: { "Cache-Control": "no-store" },
        },
      );
    // A missing path parameter is a client mistake, not a backend failure.
    return Response.json(
      { failure: "invalid_request" },
      { status: 400, headers: { "Cache-Control": "no-store" } },
    );
  }
}
