import { afterEach, expect, it, vi } from "vitest";
import { GET } from "@/app/api/connection/route";
import { backendUrl } from "@/lib/backend";
afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});
it("uses the configured backend and preserves simulation mode", async () => {
  vi.stubEnv("BACKEND_URL", "http://localhost:8011/prefix/");
  const fetcher = vi
    .fn()
    .mockResolvedValue(Response.json({ status: "ok", mode: "simulation" }));
  vi.stubGlobal("fetch", fetcher);
  const response = await GET();
  expect(fetcher).toHaveBeenCalledWith(
    "http://localhost:8011/prefix/health/live",
    expect.objectContaining({ cache: "no-store" }),
  );
  expect(await response.json()).toEqual({ status: "ok", mode: "simulation" });
  expect(response.headers.get("cache-control")).toBe("no-store");
});
it.each([
  { status: "ok", mode: ["live"] },
  { status: "ok", mode: "unknown" },
  { status: "error", mode: "live" },
])("rejects invalid health data %j", async (body) => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(body)));
  expect((await GET()).status).toBe(503);
});
it("does not leak backend failures", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockRejectedValue(new Error("private deployment details")),
  );
  const response = await GET();
  expect(response.status).toBe(503);
  expect(await response.text()).not.toContain("private deployment details");
});
it("rejects credentials and unsupported protocols", () => {
  for (const url of [
    "ftp://localhost",
    "https://user:password@example.com",
    "http://localhost?token=secret",
  ]) {
    vi.stubEnv("BACKEND_URL", url);
    expect(backendUrl).toThrow();
  }
});
