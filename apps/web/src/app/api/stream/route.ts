import type { NextRequest } from "next/server";
import { backendUrl } from "@/lib/backend";
import { ORIGIN_HEADER } from "@/lib/api/origin";
import { dataOrigin } from "@/lib/api/server";
import { recordedDataset } from "@/lib/api/fixtures";

export const dynamic = "force-dynamic";

const SSE_HEADERS = {
  "Content-Type": "text/event-stream; charset=utf-8",
  "Cache-Control": "no-store, no-transform",
  Connection: "keep-alive",
};

/**
 * Stands in for the backend event stream when reading recorded fixtures. It
 * emits the same event shape on a fixed cadence so reconnect and staleness
 * handling can be exercised without a backend.
 */
function fixtureStream(signal: AbortSignal) {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      const send = (event: string, data: unknown) =>
        controller.enqueue(
          encoder.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`),
        );

      const snapshot = () =>
        send("snapshot", {
          mode: "simulation",
          as_of: new Date().toISOString(),
          opportunities: recordedDataset().opportunities,
          exchanges: [],
          limit: 200,
        });
      snapshot();
      const timer = setInterval(snapshot, 5000);

      const stop = () => {
        clearInterval(timer);
        try {
          controller.close();
        } catch {
          // Already closed by the runtime when the client went away.
        }
      };
      signal.addEventListener("abort", stop, { once: true });
    },
  });
}

export async function GET(request: NextRequest) {
  const origin = dataOrigin();

  if (origin === "fixtures")
    return new Response(fixtureStream(request.signal), {
      headers: { ...SSE_HEADERS, [ORIGIN_HEADER]: origin },
    });

  try {
    const upstream = await fetch(`${backendUrl()}/api/v1/stream`, {
      cache: "no-store",
      headers: { accept: "text/event-stream" },
      signal: request.signal,
    });
    if (!upstream.ok || !upstream.body)
      return new Response(null, { status: 502 });
    return new Response(upstream.body, {
      headers: { ...SSE_HEADERS, [ORIGIN_HEADER]: origin },
    });
  } catch {
    // The browser reconnects on its own; a failed connection is not an error page.
    return new Response(null, { status: 503 });
  }
}
