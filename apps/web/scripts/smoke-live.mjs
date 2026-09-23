// Opt-in verification against a running live stack. Never uses recorded fixtures.
import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import { chromium, devices, expect } from "@playwright/test";

const base = process.env.DEMO_URL ?? "http://127.0.0.1:3000";
const browser = await chromium.launch();
await mkdir("test-results", { recursive: true });
try {
  for (const [name, options] of [
    ["desktop", { viewport: { width: 1440, height: 1000 } }],
    ["mobile", devices["iPhone 13"]],
  ]) {
    const context = await browser.newContext(options);
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    for (const venue of ["kalshi", "polymarket"]) {
      const response = await context.request.get(
        `${base}/api/data/markets?venue=${venue}&limit=100`,
      );
      assert(response.ok(), `${venue} catalog unavailable`);
      assert.equal(response.headers()["x-arbbot-origin"], "backend");
      const markets = await response.json();
      let selected;
      for (const market of markets) {
        assert.equal(market.mode, "live");
        const reply = await context.request.get(
          `${base}/api/data/book?market_id=${encodeURIComponent(market.id)}`,
        );
        if (!reply.ok()) continue;
        const book = await reply.json();
        if (
          (book.yes_asks.length || book.no_asks.length) &&
          Date.now() - Date.parse(book.source_at ?? book.received_at) < 30000
        ) {
          selected = market;
          break;
        }
      }
      assert(selected, `No fresh ${venue} market with depth`);
      const receipts = new Set();
      const listener = async (reply) => {
        if (reply.url().includes("/api/data/book?") && reply.ok()) {
          const book = await reply.json();
          if (book.market_id === selected.id) receipts.add(book.received_at);
        }
      };
      page.on("response", listener);
      await page.goto(`${base}/markets/${encodeURIComponent(selected.id)}`);
      await expect(
        page.getByRole("heading", { name: "Quote health" }),
      ).toBeVisible();
      await expect(page.getByRole("cell").first()).toBeVisible();
      await expect
        .poll(() => receipts.size, { timeout: 60000 })
        .toBeGreaterThan(1);
      assert.equal(
        await page.getByText("Recorded fixture data", { exact: true }).count(),
        0,
      );
      assert.equal(
        await page.evaluate(
          () => document.documentElement.scrollWidth > innerWidth,
        ),
        false,
      );
      await page.screenshot({
        path: `test-results/live-${name}-${venue}.png`,
        fullPage: true,
      });
      page.off("response", listener);
      console.log(
        `${name} ${venue}: live depth rendered; ${receipts.size} distinct worker snapshots received`,
      );
    }
    await page.goto(`${base}/markets`);
    await expect(
      page.getByText("Yes ask", { exact: true }).first(),
    ).toBeVisible();
    await page.screenshot({
      path: `test-results/live-${name}-markets.png`,
      fullPage: true,
    });
    await page.goto(`${base}/opportunities`);
    await expect(page.getByText("No opportunities right now")).toBeVisible();
    assert.deepEqual(errors, []);
    await context.close();
  }
} finally {
  await browser.close();
}
