import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/errors";
import { buildPath } from "@/lib/api/request";
import { requestOperation } from "@/lib/query/client";
import { queryKey } from "@/lib/query/keys";

function respond(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
    ...init,
  });
}

afterEach(() => vi.unstubAllGlobals());

describe("path building", () => {
  it("substitutes and encodes path parameters", () => {
    expect(
      buildPath("/api/v1/markets/{market_id}/book", {
        params: { market_id: "kalshi:CPI-T3.0" },
      }),
    ).toBe("/api/v1/markets/kalshi%3ACPI-T3.0/book");
  });

  it("omits empty query values instead of sending blanks", () => {
    expect(
      buildPath("/api/v1/markets", {
        query: { limit: 25, offset: 0, venue: null },
      }),
    ).toBe("/api/v1/markets?limit=25&offset=0");
  });

  it("refuses to build a path with a missing parameter", () => {
    expect(() =>
      buildPath("/api/v1/markets/{market_id}", { params: { market_id: "" } }),
    ).toThrow(/Missing path parameter/);
  });
});

describe("query keys", () => {
  it("produces the same key regardless of argument order or blank values", () => {
    expect(
      queryKey("markets", { query: { offset: 0, limit: 25, venue: null } }),
    ).toEqual(queryKey("markets", { query: { limit: 25, offset: 0 } }));
  });

  it("separates different arguments", () => {
    expect(queryKey("markets", { query: { limit: 25 } })).not.toEqual(
      queryKey("markets", { query: { limit: 50 } }),
    );
  });
});

describe("browser API client", () => {
  it("preserves financial values as exact strings", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        respond([{ net_profit: "0.30000000000000004", quantity: "250" }]),
      ),
    );
    const result = await requestOperation("opportunities");
    const [first] = result.data as unknown as { net_profit: string }[];
    expect(first.net_profit).toBe("0.30000000000000004");
    expect(typeof first.net_profit).toBe("string");
  });

  it("reports the data origin from the response header", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        respond([], { headers: { "x-arbbot-origin": "fixtures" } }),
      ),
    );
    expect((await requestOperation("markets")).origin).toBe("fixtures");
  });

  it("defaults to backend origin when the header is absent", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => respond([])),
    );
    expect((await requestOperation("markets")).origin).toBe("backend");
  });

  it("surfaces the failure the proxy reported", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => respond({ failure: "not_found" }, { status: 404 })),
    );
    await expect(
      requestOperation("market", { params: { market_id: "missing" } }),
    ).rejects.toMatchObject({ failure: "not_found" });
  });

  it("classifies a cancelled request rather than reporting an outage", async () => {
    const controller = new AbortController();
    controller.abort();
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new DOMException("aborted", "AbortError");
      }),
    );
    const error = await requestOperation(
      "markets",
      {},
      controller.signal,
    ).catch((thrown: unknown) => thrown);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).failure).toBe("cancelled");
  });

  it("rejects a malformed body instead of rendering partial data", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response("not json", {
            headers: { "content-type": "application/json" },
          }),
      ),
    );
    await expect(requestOperation("markets")).rejects.toMatchObject({
      failure: "invalid_response",
    });
  });

  it("passes path parameters through to the proxy", async () => {
    const fetchMock = vi.fn<
      (url: string, init?: RequestInit) => Promise<Response>
    >(async () => respond({}));
    vi.stubGlobal("fetch", fetchMock);
    await requestOperation("book", { params: { market_id: "kalshi:X" } });
    expect(fetchMock.mock.calls[0][0]).toBe(
      "/api/data/book?market_id=kalshi%3AX",
    );
  });
});
