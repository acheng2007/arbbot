import { expect, test } from "@playwright/test";

test("paired dashboard keeps prices above the fold and preserves view state", async ({
  page,
}) => {
  await page.setViewportSize(
    test.info().project.name === "mobile"
      ? { width: 390, height: 844 }
      : { width: 1440, height: 900 },
  );
  await page.goto("/");
  await expect(page).toHaveURL(/\/markets$/);
  await expect(
    page.getByRole("button", { name: "Paired markets", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  const card = page.getByRole("article", { name: /US CPI year-over-year/ });
  const prices = card.locator("dd").filter({ hasText: /^\d+¢$/ });
  await expect(prices).toHaveCount(4);
  for (const price of await prices.all()) {
    const box = await price.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.y + box!.height).toBeLessThanOrEqual(
      page.viewportSize()!.height,
    );
  }
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.getByRole("button", { name: "All markets", exact: true }).click();
  await expect(page).toHaveURL(/view=all/);
  await page.getByLabel("Search all markets").fill("payrolls");
  await expect(page.getByRole("article")).toHaveCount(1);
  await page.reload();
  await expect(
    page.getByRole("button", { name: "All markets", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByLabel("Search all markets")).toHaveValue("payrolls");
  await page
    .getByRole("button", { name: "Paired markets", exact: true })
    .click();
  await expect(
    page.getByRole("article").getByText("Unverified match"),
  ).toBeVisible();
});

test("diagnostics and extracted evidence load only on demand", async ({
  page,
}) => {
  const reads: string[] = [];
  page.on("request", (request) => reads.push(new URL(request.url()).pathname));
  await page.goto("/opportunities");
  await expect(page.getByText("Estimated net profit")).toBeVisible();
  expect(reads).not.toContain("/api/data/evaluations");
  expect(reads).not.toContain("/api/data/history");
  await page.getByText("Evaluated but not tradable", { exact: true }).click();
  await expect(
    page.getByText(/rejected in review; settlement is not equivalent/),
  ).toBeVisible();
  expect(reads).toContain("/api/data/evaluations");
  await page.goto("/markets/kalshi%3ACPIYOY-26SEP-T3.0");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  expect(reads).not.toContain("/api/data/extraction");
  await page.getByText("Extracted settlement terms", { exact: true }).click();
  await expect(page.getByText("Partially extracted")).toBeVisible();
  expect(reads).toContain("/api/data/extraction");
});

test("fixture paired filters interpret booleans before pagination", async ({
  request,
}) => {
  const response = await request.get(
    "/api/data/matches?same_event=true&exclude_rejected=true&limit=1",
  );
  expect(response.ok()).toBe(true);
  const rows = await response.json();
  expect(rows).toHaveLength(1);
  expect(rows[0].comparison.same_event).toBe(true);
  expect(rows[0].status).not.toBe("rejected");
  const excluded = await request.get(
    "/api/data/matches?same_event=true&exclude_rejected=true&market_status=closed&limit=1",
  );
  expect(await excluded.json()).toEqual([]);
});

test("US NO prices are labeled as short collateral", async ({ page }) => {
  await page.route("**/api/data/market?*", async (route) => {
    const response = await route.fetch();
    const market = await response.json();
    if (market.venue === "polymarket") market.venue = "polymarket_us";
    await route.fulfill({ response, json: market });
  });
  await page.goto("/markets");
  await expect(
    page
      .getByRole("article", { name: /US CPI year-over-year/ })
      .getByText("NO short collateral", { exact: true }),
  ).toBeVisible();
  await expect(
    page
      .getByRole("article", { name: /US CPI year-over-year/ })
      .getByRole("link", { name: "Polymarket US", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});

test("unverified paired prices never imply verified arbitrage", async ({
  page,
}) => {
  await page.route("**/api/data/matches?*", async (route) => {
    const response = await route.fetch();
    const pairs = await response.json();
    await route.fulfill({
      response,
      json: pairs.map((pair: Record<string, unknown>) => ({
        ...pair,
        status: "candidate",
      })),
    });
  });
  await page.goto("/markets");
  await expect(
    page
      .getByRole("article", { name: /US CPI year-over-year/ })
      .getByText("Inspect assessment"),
  ).toBeVisible();
  await expect(
    page
      .getByRole("article", { name: /US CPI year-over-year/ })
      .getByText("Unverified match"),
  ).toBeVisible();
  await expect(page.getByText("Verified in review")).toHaveCount(0);
  await expect(page.getByText("43¢", { exact: true })).toBeVisible();
});
