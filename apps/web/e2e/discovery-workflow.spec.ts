import { expect, test } from "@playwright/test";
import { recordedDataset } from "../src/lib/api/fixtures";

test("discovery relationship controls and opportunity views are shareable", async ({
  page,
}) => {
  await page.goto("/markets");
  await page.getByRole("button", { name: "Filters", exact: true }).click();
  await page
    .getByLabel("Relationship", { exact: true })
    .selectOption("unverified");
  await expect(page).toHaveURL(/relationship=unverified/);
  await expect(
    page.getByRole("article").getByText("Unverified match"),
  ).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("Relationship", { exact: true })).toHaveValue(
    "unverified",
  );
  await page.goto("/opportunities?view=potential&category=politics&q=election");
  await expect(
    page.getByRole("button", { name: "Potential", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByLabel("Search opportunities")).toHaveValue("election");
  await expect(page.getByLabel("Opportunity category")).toHaveValue("politics");
  await expect(
    page.getByText("No potential price gaps right now"),
  ).toBeVisible();
  await expect(page.getByText(/not qualified profit estimates/)).toBeVisible();
});

test("unknown potential costs stay unknown and withdrawn inputs have explicit history", async ({
  page,
}) => {
  const markets = recordedDataset()
    .markets.slice(0, 2)
    .map((m) => ({ ...m, settlement_asset: "USD" }));
  const now = new Date();
  const item = {
    id: "potential-ui-fixture",
    match_id: "match-cpi-2026-09",
    mode: "simulation",
    feed_origin: "synthetic_recording",
    evaluated_at: now.toISOString(),
    valid_until: new Date(now.getTime() + 30000).toISOString(),
    market_ids: markets.map((m) => m.id),
    book_ids: ["a", "b"],
    terms_hashes: markets.map((m) => m.terms_hash),
    fee_revision_ids: [],
    outcomes: ["yes", "no"],
    quantity: "10",
    acquisition_cost: "8.40",
    ordinary_payout_assumption: "10",
    gross_spread: "1.60",
    fee_bound: null,
    estimated_net_spread: null,
    capital_required: null,
    qualification: {
      status: "incomplete",
      basis: "automatic_rules",
      blocked_reasons: ["applicable_sources_incomplete"],
    },
    unresolved_reasons: [
      "applicable_sources_incomplete",
      "public_costs_unavailable",
    ],
    assumptions: [
      "Explicitly synthetic UI recording. Ordinary outcomes are assumed; settlement is not qualified.",
    ],
  };
  let withdrawn = false;
  const headers = { "x-arbbot-origin": "fixtures" };
  await page.route("**/api/data/potentialOpportunities?**", (route) =>
    route.fulfill({ status: 200, headers, json: [item] }),
  );
  await page.route("**/api/data/potentialOpportunity?**", (route) => {
    const historical =
      new URL(route.request().url()).searchParams.get("historical") === "true";
    return route.fulfill(
      withdrawn && !historical
        ? { status: 404, json: { failure: "not_found" } }
        : { status: 200, headers, json: item },
    );
  });
  await page.goto("/opportunities?view=potential");
  await expect(
    page.getByRole("article").getByText("Unknown", { exact: true }),
  ).toHaveCount(2);
  await page.getByRole("link", { name: markets[0].title, exact: true }).click();
  await expect(
    page.getByText(/Estimated ordinary net spread: Unknown/),
  ).toBeVisible();
  withdrawn = true;
  await page.reload();
  await page.getByRole("button", { name: "Inspect historical result" }).click();
  await expect(page.getByText(/Historical inputs only/)).toBeVisible();
  await expect(
    page.getByText(/Estimated ordinary net spread: Unknown/),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: `/tmp/arbbot-discovery-potential-${test.info().project.name}.png`,
    fullPage: true,
  });
});
