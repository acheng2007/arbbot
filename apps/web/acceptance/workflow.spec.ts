import { expect, test } from "@playwright/test";
import { readFileSync, writeFileSync, renameSync } from "node:fs";

function phase(value: "baseline" | "adverse") {
  const path = process.env.ARBBOT_ACCEPTANCE_CONTROL!;
  const state = JSON.parse(readFileSync(path, "utf8"));
  writeFileSync(`${path}.tmp`, JSON.stringify({ ...state, phase: value, epoch: state.epoch + 1 }));
  renameSync(`${path}.tmp`, path);
}

test("recorded worker estimates, exact details, broad browsing and SSE recovery", async ({ page }) => {
  phase("baseline");
  await page.goto("/opportunities");
  await expect(page.getByText("Offline recorded acceptance data.")).toBeVisible();
  await expect(page.getByText("Synthetic recording").first()).toBeVisible();
  await expect(page.getByText("Short instrument (NO)").first()).toBeVisible();
  await expect(page.getByText("Gross collateral").first()).toBeVisible();
  await expect(page.getByText("Best estimated net result:", { exact: false }).first()).toBeVisible();
  await page.getByRole("link", { name: "Full calculation and assumptions" }).first().click();
  await expect(page.getByText("Payout in every settlement outcome")).toBeVisible();
  await expect(page.getByText("Short proceeds").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "Recorded review" })).toBeVisible();
  await expect(page.getByText("Fee policy snapshot", { exact: true })).toHaveCount(2);
  await expect(page.getByText("Fee per contract", { exact: true })).toHaveCount(0);
  // A continuously replaced estimate remains inspectable with its audit reasons.
  if (await page.getByText("From history", { exact: true }).isVisible()) {
    await expect(page.getByRole("region", { name: "Opportunity invalidation" })).toBeVisible();
  }
  await expect(page.getByText("Live feed", { exact: true })).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: `${process.env.ARBBOT_ACCEPTANCE_OUTPUT}/${test.info().project.name}-calculation.png` });
  await page.getByRole("heading", { name: "Recorded review" }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${process.env.ARBBOT_ACCEPTANCE_OUTPUT}/${test.info().project.name}-review.png` });

  await page.goto("/markets?q=synthetic-3-counterpart-204&category=acceptance&status=open");
  await expect(page.getByRole("heading", { name: "SYNTHETIC: Scenario 3" }).first()).toBeVisible();
  await expect(page.getByText("No markets match these filters")).toHaveCount(0);
  await page.goto("/markets/kalshi%3ASYN-3");
  await expect(page.getByRole("heading", { name: "Proposed counterparts" })).toBeVisible();
  const pages = page.getByRole("navigation", { name: "Counterpart pages" });
  for (let index = 0; index < 10; index += 1) {
    await pages.getByRole("button", { name: "Next" }).click();
    await expect(pages).toContainText(`Page ${index + 2}`);
  }
  await expect(pages).toContainText("Page 11");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: `${process.env.ARBBOT_ACCEPTANCE_OUTPUT}/${test.info().project.name}-counterparts.png`, fullPage: true });

  await page.goto("/opportunities");
  await expect(page.getByText("Short instrument (NO)").first()).toBeVisible();
  phase("adverse");
  await expect(page.getByText("No opportunities right now")).toBeVisible();
  await expect(page.getByText("Short instrument (NO)")).toHaveCount(0);
  phase("baseline");
  await expect(page.getByText("Short instrument (NO)").first()).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: `${process.env.ARBBOT_ACCEPTANCE_OUTPUT}/${test.info().project.name}-opportunities.png` });
});

test("connected loading, retry, and stale quote states remain understandable", async ({ page }) => {
  // Hold actual backend reads to expose loading, then simulate a transport failure.
  // Successful responses still come from the persistent PostgreSQL-backed worker.
  let release!: () => void;
  const held = new Promise<void>((resolve) => { release = resolve; });
  let failing = true;
  // Exercise manual retry while SSE is unavailable. Otherwise a real snapshot
  // can recover the query before the user has time to press the retry button.
  await page.route("**/api/stream", (route) => route.abort());
  await page.route("**/api/data/opportunities*", async (route) => {
    await held;
    if (failing) await route.fulfill({ status: 503, json: { failure: "unreachable" } });
    else await route.continue();
  });
  await page.goto("/opportunities");
  await expect(page.getByText("Loading opportunities", { exact: true })).toBeVisible();
  await page.getByText("Loading opportunities", { exact: true }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${process.env.ARBBOT_ACCEPTANCE_OUTPUT}/${test.info().project.name}-loading.png` });
  release();
  await expect(page.getByRole("main").getByRole("alert")).toContainText("could not be loaded");
  await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
  await page.getByRole("main").getByRole("alert").scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${process.env.ARBBOT_ACCEPTANCE_OUTPUT}/${test.info().project.name}-error.png` });
  failing = false;
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(page.getByRole("main").getByRole("alert")).toHaveCount(0);
  await expect(page.getByText("Offline recorded acceptance data.")).toBeVisible();

  // This book is genuinely stale in the exchange recording, not patched in the UI.
  await page.goto("/markets/polymarket_us%3Asynthetic-4");
  await expect(page.getByRole("heading", { name: "Quote health" })).toBeVisible();
  await expect(page.getByText(/Stale quote/).first()).toBeVisible();
  await expect(page.getByText("Synthetic recording").first()).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.getByRole("heading", { name: "Quote health" }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${process.env.ARBBOT_ACCEPTANCE_OUTPUT}/${test.info().project.name}-stale.png` });
});
