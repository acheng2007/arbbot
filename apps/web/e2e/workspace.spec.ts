import { expect, test } from "@playwright/test";

test("market evidence leads through review to an opportunity estimate", async ({
  page,
}) => {
  await page.goto("/markets");

  await expect(page.getByText("Recorded fixture data.")).toBeVisible();
  await expect(page.getByText("Simulation").first()).toBeVisible();

  await page
    .getByRole("link", { name: /US CPI year-over-year above 3\.0%/ })
    .click();
  await expect(page.getByText("Kalshi original terms")).toBeVisible();
  await expect(page.getByText("Quote health")).toBeVisible();
  await expect(page.getByText("Partially extracted")).toBeVisible();

  await page.getByRole("link", { name: "Comparisons" }).click();
  const pair = page.getByRole("link", {
    name: /US CPI year-over-year above 3\.0%/,
  });
  await expect(pair).toContainText("Verified in review");
  await pair.click();

  await expect(page.getByText("Recorded review")).toBeVisible();
  await expect(page.getByText("Unresolved assumptions")).toBeVisible();
  await expect(page.getByText(/resolves 50\/50/).first()).toBeVisible();

  await page.getByRole("link", { name: "Opportunities" }).click();
  await expect(page.getByText("Quote-supported estimate")).toBeVisible();
  await page
    .getByRole("link", { name: /Full calculation and assumptions/ })
    .click();

  await expect(page.getByText("Net profit after all costs")).toBeVisible();
  await expect(
    page.getByText("Payout in every settlement outcome"),
  ).toBeVisible();
  await expect(page.getByText("Execution assumptions")).toBeVisible();
  await expect(
    page.getByText(/No order is placed by this system/),
  ).toBeVisible();
});
