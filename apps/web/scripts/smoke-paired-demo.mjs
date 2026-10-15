// Opt-in browser check against the running backend and live demo.
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
      const book = await response.json();
      const values = receipts.get(book.market_id) ?? new Set();
      values.add(book.received_at);
      receipts.set(book.market_id, values);
    });
    await page.goto("http://localhost:3000/markets");
    const section = page.getByRole("region", {
      name: "Cross-exchange predictions",
    });
    await expect(section).toBeVisible();
    await expect(
      section.getByRole("heading", { name: "Polymarket", exact: true }),
    ).toBeVisible();
    await expect(
      section.getByRole("heading", { name: "Kalshi", exact: true }),
    ).toBeVisible();
    await expect(section.getByText(/Settlement terms differ/)).toBeVisible();
    await expect(section.getByText("Yes ask", { exact: true })).toHaveCount(2);
    const links = await section
      .locator('a[href^="/markets/"]')
      .evaluateAll((items) =>
        items.map((item) =>
          decodeURIComponent(item.getAttribute("href").slice(9)),
        ),
      );
    assert.equal(links.length, 2);
    await expect
      .poll(() => links.every((id) => (receipts.get(id)?.size ?? 0) >= 2), {
        timeout: 60000,
      })
      .toBe(true);
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      ),
      false,
    );
    await page.screenshot({ path: `test-results/paired-demo-${name}.png` });
    console.log(
      `${name}: both venue panels and changing live snapshots verified`,
    );
    await page.close();
  }
} finally {
  await browser.close();
}
