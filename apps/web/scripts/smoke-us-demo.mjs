// Opt-in check against the real two-venue local demo.
import assert from "node:assert/strict";
import { chromium, devices, expect } from "@playwright/test";
const browser = await chromium.launch();
try {
  for (const [name, options] of [
    ["desktop", { viewport: { width: 1440, height: 1000 } }],
    ["mobile", devices["iPhone 13"]],
  ]) {
    const page = await browser.newPage(options);
    const receipts = new Map();
    page.on("response", async (response) => {
      if (!response.url().includes("/api/data/book?") || !response.ok()) return;
      const book = await response.json().catch(() => null);
      if (!book) return;
      const values = receipts.get(book.market_id) ?? new Set();
      values.add(book.received_at);
      receipts.set(book.market_id, values);
    });
    await page.goto("http://localhost:3000/markets");
    const section = page.getByRole("region", { name: "Cross-exchange predictions" });
    await expect(section).toBeVisible();
    const card = section.getByRole("article").filter({hasText: "Los Angeles Dodgers"});
    await expect(card).toHaveCount(1);
    await expect(card.getByRole("heading", {name: "Kalshi", exact: true})).toBeVisible();
    await expect(card.getByRole("heading", {name: "Polymarket US", exact: true})).toBeVisible();
    await expect(card.getByText(/not a verified arbitrage opportunity/)).toBeVisible();
    await expect(card.getByText("Yes ask", {exact: true})).toHaveCount(2);
    await expect(card.getByText("No ask", {exact: true})).toHaveCount(2);
    await expect(card.getByText(/collateral cost of shorting/)).toBeVisible();
    const links = await card.locator('a[href^="/markets/"]').evaluateAll(items =>
      items.map(item => decodeURIComponent(item.getAttribute("href").slice(9))));
    assert.equal(links.length, 2);
    assert(links.some(id => id.startsWith("polymarket_us:")));
    assert(links.some(id => id === "kalshi:KXMLB-26-LAD"));
    await expect.poll(() => links.every(id => (receipts.get(id)?.size ?? 0) >= 2), {timeout: 60000}).toBe(true);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    await card.scrollIntoViewIfNeeded();
    await page.screenshot({path: `test-results/us-demo-${name}.png`});
    await card.getByRole("link", {name: /Inspect settlement review/}).click();
    await expect(page.getByRole("heading", {level: 1})).toContainText("Los Angeles D");
    await expect(page.getByText("Terms incomplete", {exact: true})).toBeVisible();
    await expect(page.getByText("Polymarket US original terms", {exact: true})).toBeVisible();
    await expect(page.getByText(/last fair market prices/).first()).toBeVisible();
    console.log(`${name}: real Kalshi/Polymarket US paired quotes, refresh, review, and layout passed`);
    await page.close();
  }
} finally { await browser.close(); }
