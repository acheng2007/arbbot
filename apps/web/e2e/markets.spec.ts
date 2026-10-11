import { expect, test } from "@playwright/test";

test("quotes refresh without navigation and recover after a failed refresh", async ({
  page,
}) => {
  let phase = "initial";
  await page.route("**/api/data/book?*", async (route) => {
    if (phase === "failed") {
      await route.fulfill({ status: 503, json: { failure: "backend_error" } });
      return;
    }
    const response = await route.fetch();
    const book = await response.json();
    book.yes_asks = [
      { price: phase === "initial" ? "0.1234" : "0.2345", size: "17" },
    ];
    await route.fulfill({ response, json: book });
  });
  await page.goto("/markets/kalshi%3ACPIYOY-26SEP-T3.0");
  await expect(
    page.getByRole("cell", { name: "12.34¢", exact: true }),
  ).toBeVisible();
  phase = "updated";
  await expect(
    page.getByRole("cell", { name: "23.45¢", exact: true }),
  ).toBeVisible({ timeout: 12000 });
  phase = "failed";
  await expect(page.getByRole("main").getByRole("alert")).toContainText(
    "This view could not be loaded",
    { timeout: 15000 },
  );
  await expect(
    page.getByRole("cell", { name: "23.45¢", exact: true }),
  ).toHaveCount(0);
  phase = "recovered";
  await expect(
    page.getByRole("cell", { name: "23.45¢", exact: true }),
  ).toBeVisible({ timeout: 12000 });
});

test("filters are shareable through the address bar", async ({ page }) => {
  await page.goto("/markets");
  await expect(
    page.getByRole("link", { name: /NYC high temperature/ }),
  ).toBeVisible();

  await page.getByLabel("Venue").selectOption("kalshi");
  await expect(page).toHaveURL(/venue=kalshi/);
  await expect(
    page.getByRole("link", { name: /Will US CPI YoY/ }),
  ).toBeVisible();

  await page.getByLabel("Search the loaded page").fill("payrolls");
  await expect(page).toHaveURL(/q=payrolls/);
  await expect(
    page.getByRole("link", { name: /nonfarm payrolls/ }),
  ).toBeVisible();

  // Reloading the shared address must reproduce the same view.
  await page.reload();
  await expect(page.getByLabel("Venue")).toHaveValue("kalshi");
  await expect(page.getByLabel("Search the loaded page")).toHaveValue(
    "payrolls",
  );

  await page.getByRole("button", { name: "Clear filters" }).click();
  await expect(page).toHaveURL(/\/markets$/);
});

test("a search with no matches explains itself", async ({ page }) => {
  await page.goto("/markets?q=nothing-matches-this");
  await expect(page.getByText("No markets match these filters")).toBeVisible();
});

test("source detail shows original terms, extraction gaps, and quote health", async ({
  page,
}) => {
  await page.goto("/markets");
  await page
    .getByRole("link", { name: /US CPI year-over-year above 3\.0%/ })
    .click();

  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "US CPI year-over-year above 3.0%",
  );
  await expect(page.getByText("Kalshi original terms")).toBeVisible();
  await expect(
    page.getByText(/If the BLS does not publish the September 2026 release/),
  ).toBeVisible();

  await expect(page.getByText("Quote health")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Yes asks" })).toBeVisible();

  await expect(page.getByText("Partially extracted")).toBeVisible();
  await expect(page.getByText("Fields not determined")).toBeVisible();
  await expect(
    page.getByText(/A missing field never counts toward equivalence/),
  ).toBeVisible();
});

test("a market without depth says so rather than showing a blank book", async ({
  page,
}) => {
  await page.goto("/markets/kalshi%3APAYROLLS-26OCT-T150");
  await expect(page.getByText("No executable depth")).toBeVisible();
  await expect(page.getByText("Not supported")).toBeVisible();
});

test("a market that does not exist reports a clean failure", async ({
  page,
}) => {
  await page.goto("/markets/kalshi%3ANOPE");
  await expect(page.getByRole("main").getByRole("alert")).toContainText(
    "That record does not exist",
  );
});

test("prediction cards show both venue prices together", async ({ page }) => {
  await page.goto("/markets");
  const prediction = page.getByRole("article", {
    name: /US CPI year-over-year above/,
  });
  await expect(
    prediction.getByRole("heading", { name: "Polymarket International", exact: true }),
  ).toBeVisible();
  await expect(
    prediction.getByRole("heading", { name: "Kalshi", exact: true }),
  ).toBeVisible();
  await expect(prediction.getByText("Yes ask", { exact: true })).toHaveCount(2);
  await expect(prediction.getByText("No ask", { exact: true })).toHaveCount(2);
  await expect(prediction.getByText("Loading prices...")).toHaveCount(0);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: `test-results/predictions-${test.info().project.name}.png`,
    fullPage: true,
  });
});
