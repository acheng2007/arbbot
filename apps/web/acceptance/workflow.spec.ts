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
  await expect(page.getByText("Live feed", { exact: true })).toHaveCount(0);
  await page.screenshot({ path: `${process.env.ARBBOT_ACCEPTANCE_OUTPUT}/${test.info().project.name}-calculation.png`, fullPage: true });

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
  await page.screenshot({ path: `${process.env.ARBBOT_ACCEPTANCE_OUTPUT}/${test.info().project.name}-opportunities.png`, fullPage: true });
});
