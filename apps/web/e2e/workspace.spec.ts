import { expect, test } from "@playwright/test";

test("market evidence leads through review to an opportunity estimate", async ({
  page,
}) => {
  await page.goto("/markets");

  await expect(page.getByText(/Recorded fixture data/)).toBeVisible();
  await expect(page.getByText("Simulation").first()).toBeVisible();

  await page.getByRole("link", { name: "Kalshi", exact: true }).click();
  await page.getByText("Source documents", { exact: true }).click();
  await page.getByText("Extracted settlement terms", { exact: true }).click();
  await expect(page.getByText("Kalshi original terms")).toBeVisible();
  await expect(page.getByText("Quote health")).toBeVisible();
  await expect(page.getByText("Partially extracted")).toBeVisible();

  await page.getByRole("link", { name: "Comparisons" }).click();
  const pair = page.getByRole("link", {
    name: /US CPI year-over-year above 3\.0%/,
  });
  await expect(pair).toContainText("Verified in review");
  await pair.click();

  await page.getByText("Review evidence", { exact: true }).click();
  await page.getByText("Settlement terms", { exact: true }).click();
  await expect(page.getByText("Recorded review")).toBeVisible();
  await expect(page.getByText("Unresolved assumptions")).toBeVisible();
  await expect(page.getByText(/resolves 50\/50/).first()).toBeVisible();

  await page.getByRole("link", { name: "Opportunities" }).click();
  await expect(page.getByText("Estimated net profit")).toBeVisible();
  await page
    .getByRole("link", { name: /View calculation and assumptions/ })
    .click();

  await page.getByText("Cost and result", { exact: true }).click();
  await page.getByText("Settlement scenarios", { exact: true }).click();
  await page.getByText("Execution assumptions", { exact: true }).click();
  await expect(page.getByText("Net profit after all costs")).toBeVisible();
  await expect(
    page.getByText("Payout in every settlement outcome"),
  ).toBeVisible();
  await expect(page.getByText("Execution assumptions")).toBeVisible();
  await expect(
    page.getByText(/No order is placed by this system/),
  ).toBeVisible();
});
