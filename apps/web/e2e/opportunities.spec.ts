import { expect, test, type Page } from "@playwright/test";

/** Reads the fixture payload the app would normally receive, then rewrites it. */
async function patchOpportunities(
  page: Page,
  patch: (entries: Record<string, unknown>[]) => Record<string, unknown>[],
) {
  await page.route("**/api/data/opportunities*", async (route) => {
    const response = await route.fetch();
    const body = (await response.json()) as Record<string, unknown>[];
    await route.fulfill({ json: patch(body) });
  });
}

test("an estimate is presented with its costs, evidence, and caveats", async ({
  page,
}) => {
  await page.goto("/opportunities");

  await expect(page.getByText("Recorded fixture data.")).toBeVisible();
  await expect(page.getByText("Quote-supported estimate")).toBeVisible();
  await expect(page.getByText(/not guaranteed profit/)).toBeVisible();

  await page
    .getByRole("link", { name: /Full calculation and assumptions/ })
    .click();

  // Costs must be separable, not rolled into one number.
  await expect(page.getByText("Executable depth cost")).toBeVisible();
  await expect(page.getByText("Fees", { exact: true })).toBeVisible();
  await expect(page.getByText("Slippage allowance")).toBeVisible();
  await expect(page.getByText("Net profit after all costs")).toBeVisible();

  await expect(
    page.getByText("Payout in every settlement outcome"),
  ).toBeVisible();
  await expect(page.getByText("Execution assumptions")).toBeVisible();
  await expect(
    page.getByText(/No order is placed by this system/),
  ).toBeVisible();

  // Every estimate must be traceable back to the terms it rests on.
  await page
    .getByRole("link", { name: /Inspect the contract comparison/ })
    .click();
  await expect(page.getByText("Recorded review")).toBeVisible();
});

test("exact decimal strings reach the screen unrounded", async ({ page }) => {
  await patchOpportunities(page, (entries) =>
    entries.map((entry) => ({
      ...entry,
      net_profit: "0.30000000000000004",
      return_on_capital: "0.00913333",
    })),
  );
  await page.goto("/opportunities/opp-cpi-2026-09-01");
  await expect(page.getByText("$0.30000000000000004").first()).toBeVisible();
  await expect(page.getByText(/0\.913333%/).first()).toBeVisible();
});

test("an expired quote window is never shown as still valid", async ({
  page,
}) => {
  await patchOpportunities(page, (entries) =>
    entries.map((entry) => ({
      ...entry,
      valid_until: new Date(Date.now() - 45_000).toISOString(),
    })),
  );
  await page.goto("/opportunities");
  await expect(page.getByText(/^Expired /)).toBeVisible();
  await expect(page.getByText(/^Valid for /)).toHaveCount(0);
});

test("a dropped stream stops the page claiming the figures are current", async ({
  page,
}) => {
  await page.route("**/api/stream", (route) => route.abort());
  await page.goto("/opportunities");

  const banner = page.getByText("Live updates disconnected, retrying.");
  await expect(banner).toBeVisible();
  await expect(page.getByText(/No snapshot has arrived yet/)).toBeVisible();
  await expect(page.getByText("Live updates connected")).toHaveCount(0);
});

test("the stream reconnects and confirms the data again", async ({ page }) => {
  let allow = false;
  await page.route("**/api/stream", async (route) => {
    if (!allow) return route.abort();
    await route.continue();
  });

  await page.goto("/opportunities");
  await expect(
    page.getByText("Live updates disconnected, retrying."),
  ).toBeVisible();

  allow = true;
  await expect(page.getByText("Live updates connected")).toBeVisible({
    timeout: 20_000,
  });
});

test("pairs that produced no opportunity explain why", async ({ page }) => {
  await page.goto("/opportunities");
  await expect(page.getByText("Evaluated but not tradable")).toBeVisible();
  await expect(
    page.getByText(/rejected in review; settlement is not equivalent/),
  ).toBeVisible();
  await expect(
    page.getByText(/No executable quotes are available on either venue/),
  ).toBeVisible();
});

test("an empty result set reads as normal rather than broken", async ({
  page,
}) => {
  await patchOpportunities(page, () => []);
  await page.goto("/opportunities");
  await expect(page.getByText("No opportunities right now")).toBeVisible();
  await expect(
    page.getByText(/This is the normal state most of the time/),
  ).toBeVisible();
});

test("a failing API produces a retryable error, not a blank page", async ({
  page,
}) => {
  await page.route("**/api/data/opportunities*", (route) =>
    route.fulfill({ status: 503, json: { failure: "unreachable" } }),
  );
  await page.goto("/opportunities");
  await expect(page.getByRole("main").getByRole("alert")).toContainText(
    "could not be loaded",
  );
  await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
});

test("a backend snapshot refreshes displayed opportunities", async ({
  page,
}) => {
  let reads = 0;
  let changed = false;
  let sendSnapshot!: () => void;
  const snapshotReady = new Promise<void>((resolve) => {
    sendSnapshot = resolve;
  });
  await page.route("**/api/data/opportunities*", async (route) => {
    reads += 1;
    const response = await route.fetch();
    const entries = await response.json();
    await route.fulfill({ json: changed ? [] : entries });
  });
  await page.route("**/api/stream", async (route) => {
    await snapshotReady;
    await route.fulfill({
      contentType: "text/event-stream",
      body: `event: snapshot\ndata: ${JSON.stringify({
        mode: "simulation",
        as_of: new Date().toISOString(),
        opportunities: [],
        exchanges: [],
        limit: 200,
      })}\n\n`,
    });
  });
  await page.goto("/opportunities");
  await expect(page.getByText("Quote-supported estimate")).toBeVisible();
  const initialReads = reads;
  changed = true;
  sendSnapshot();
  await expect(page.getByText("No opportunities right now")).toBeVisible();
  expect(reads).toBeGreaterThan(initialReads);
});

test("a catalog contract without monitored quotes has a useful empty state", async ({
  page,
}) => {
  await page.route("**/api/data/book?*", (route) =>
    route.fulfill({ status: 404, json: { failure: "not_found" } }),
  );
  await page.goto("/markets/kalshi%3ACPIYOY-26SEP-T3.0");
  await expect(page.getByText("No monitored order book")).toBeVisible();
  await expect(page.getByText("This view could not be loaded")).toHaveCount(0);
});
