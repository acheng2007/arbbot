import { backendUrl } from "@/lib/backend";
export async function GET() {
  try {
    const response = await fetch(`${backendUrl()}/health/live`, {
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    });
    if (!response.ok) throw new Error("Backend unavailable");
    const body: unknown = await response.json();
    if (
      !body ||
      typeof body !== "object" ||
      !("status" in body) ||
      body.status !== "ok" ||
      !("mode" in body) ||
      (body.mode !== "simulation" && body.mode !== "live")
    )
      throw new Error("Unexpected health response");
    return Response.json(
      { status: "ok", mode: body.mode },
      { headers: { "Cache-Control": "no-store" } },
    );
  } catch {
    return Response.json(
      { error: "Unable to reach the configured backend" },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }
}
