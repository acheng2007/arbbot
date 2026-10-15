import { expect, test } from "@playwright/test";

test("advisory findings and captured evidence remain separate from review", async ({
  page,
}) => {
  await page.route("**/api/data/match?**", async (route) => {
    const result = await route.fetch();
    const body = await result.json();
    body.classification = {
      state: "fresh",
      supports_candidate: true,
      recorded: true,
      requested_model: "typesafe/jev-1.13",
      question_version: "counterparts-v1",
      event: {
        choice: "same_event",
        confidence: 0.95,
        probabilities: { same_event: 0.9 },
      },
      clauses: {
        cancellation: {
          choice: "different_meaning",
          confidence: 0.9,
          probabilities: { different_meaning: 0.9 },
          evidence_ids: ["span"],
        },
      },
      evidence: [
        {
          id: "span",
          side: "left",
          clause: "cancellation",
          quotation: "Cancellation refunds all contracts.",
          start: 0,
          end: 34,
          applicability: "market_terms",
        },
      ],
      limitations: ["Captured excerpts may omit context."],
    };
    await route.fulfill({ response: result, json: body });
  });
  await page.goto("/matches/match-payrolls-2026-10");
  await page
    .getByText("AI classification and matching rationale", { exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "AI suggests same event" }),
  ).toBeVisible();
  await expect(page.getByText("Candidate, not verified")).toBeVisible();
  await expect(page.getByText("No review recorded")).toBeVisible();
  await page
    .getByText("cancellation: different meaning", { exact: true })
    .click();
  await expect(
    page.getByText("Cancellation refunds all contracts."),
  ).toBeVisible();
  await expect(page.getByText(/not measured accuracy/)).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: `/tmp/arbbot-jev-${test.info().project.name}.png`,
    fullPage: true,
  });
});

test("pending, stale and unavailable states stay readable", async ({
  page,
}) => {
  for (const state of ["pending", "stale", "unavailable"]) {
    await page.route("**/api/data/match?**", async (route) => {
      const result = await route.fetch();
      const body = await result.json();
      body.classification = {
        state,
        supports_candidate: false,
        clauses: {},
        evidence: [],
        limitations: [],
        error: state === "unavailable" ? "provider_http_503" : null,
      };
      await route.fulfill({ response: result, json: body });
    });
    await page.goto("/matches/match-payrolls-2026-10");
    await page
      .getByText("AI classification and matching rationale", { exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: `AI classification ${state}` }),
    ).toBeVisible();
    await expect(page.getByText("No review recorded")).toBeVisible();
    await page.unroute("**/api/data/match?**");
  }
});

test("withdrawn AI-only pairs retain a readable stale advisory result", async ({
  page,
}) => {
  await page.route("**/api/data/match?**", (route) =>
    route.fulfill({ status: 404, json: { failure: "not_found" } }),
  );
  await page.route("**/api/data/classificationDetail?**", (route) =>
    route.fulfill({
      status: 200,
      headers: { "x-arbbot-origin": "fixtures" },
      json: {
        state: "stale",
        supports_candidate: false,
        clauses: {},
        evidence: [],
        limitations: [],
      },
    }),
  );
  await page.goto("/matches/withdrawn-ai-pair");
  await expect(page.getByText("This pair is not available")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "AI classification stale" }),
  ).toBeVisible();
  await expect(page.getByText(/no longer contributes/)).toBeVisible();
});
