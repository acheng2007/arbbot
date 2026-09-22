import { execFileSync } from "node:child_process";
import { describe, expect, it } from "vitest";
import { API_OPERATIONS } from "@/lib/api/schema";

// Vitest runs from the web package root; import.meta.url is not a file URL under jsdom.
const webRoot = process.cwd();

describe("generated API client", () => {
  it("matches docs/openapi.json", () => {
    // Fails if the committed schema drifts from the OpenAPI document.
    expect(() =>
      execFileSync("node", ["scripts/generate-api.mjs", "--check"], {
        cwd: webRoot,
        stdio: "pipe",
      }),
    ).not.toThrow();
  });

  it("exposes the routes the proxy relies on", () => {
    expect(API_OPERATIONS.market.route).toBe("/api/v1/markets/{market_id}");
    expect(API_OPERATIONS.market.params).toEqual(["market_id"]);
    expect(API_OPERATIONS.markets.query).toEqual(["limit", "offset", "venue"]);
  });
});
