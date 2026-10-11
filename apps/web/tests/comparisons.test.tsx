import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DifferenceTable } from "@/features/comparisons/difference-table";
import { ReviewPanel } from "@/features/comparisons/review-panel";
import { recordedDataset } from "@/lib/api/fixtures";
import type { Comparison, Match } from "@/lib/api/schema";

const dataset = recordedDataset(new Date("2026-09-21T06:00:00Z"));

function matchNamed(id: string): Match {
  const match = dataset.matches.find((entry) => entry.id === id);
  if (!match) throw new Error(`fixture ${id} is missing`);
  return match;
}

function comparisonFor(id: string): Comparison {
  const comparison = matchNamed(id).comparison;
  if (!comparison) throw new Error(`fixture ${id} has no comparison`);
  return comparison;
}

function fieldCard(field: string) {
  const card = document.querySelector(`[data-field="${field}"]`);
  if (!card) throw new Error(`no card rendered for ${field}`);
  return card as HTMLElement;
}

describe("difference table", () => {
  it("lists unresolved fields before agreeing ones", () => {
    render(<DifferenceTable comparison={comparisonFor("match-cpi-2026-09")} />);
    const statuses = [...document.querySelectorAll("[data-status]")].map(
      (node) => node.getAttribute("data-status"),
    );
    expect(statuses.indexOf("equal")).toBeGreaterThan(
      statuses.lastIndexOf("different"),
    );
  });

  it("marks a differing field rather than smoothing it over", () => {
    render(<DifferenceTable comparison={comparisonFor("match-cpi-2026-09")} />);
    const card = fieldCard("cancellation");
    expect(within(card).getByText("Differs")).toBeVisible();
    expect(within(card).getByText(/resolves 50\/50/)).toBeVisible();
  });

  it("says a field was not determined instead of leaving it blank", () => {
    render(<DifferenceTable comparison={comparisonFor("match-cpi-2026-09")} />);
    const card = fieldCard("observation_window");
    expect(within(card).getByText("Unknown")).toBeVisible();
    expect(
      within(card).getAllByText("Not extracted from this contract."),
    ).toHaveLength(2);
  });

  it("shows the exact source quotation behind each extracted value", () => {
    render(<DifferenceTable comparison={comparisonFor("match-cpi-2026-09")} />);
    const card = fieldCard("value_version");
    expect(
      within(card).getByText(
        /Revisions published after the initial release are disregarded/,
      ),
    ).toBeVisible();
    expect(within(card).getAllByText(/Quoted from the/).length).toBe(2);
  });

  it("handles a pair with only one extracted definition", () => {
    render(
      <DifferenceTable comparison={comparisonFor("match-payrolls-2026-10")} />,
    );
    expect(
      screen.getAllByText("Not extracted from this contract.").length,
    ).toBeGreaterThan(0);
  });

  it("labels each column with the venue it belongs to", () => {
    render(
      <DifferenceTable
        comparison={comparisonFor("match-cpi-2026-09")}
        leftLabel="Kalshi"
        rightLabel="Polymarket"
      />,
    );
    expect(screen.getAllByText("Kalshi").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Polymarket").length).toBeGreaterThan(0);
  });
});

describe("review panel", () => {
  const market = (id: string) => dataset.markets.find((m) => m.id === id);

  it("presents a rejection as a rejection", () => {
    const match = matchNamed("match-fed-2026-11");
    render(
      <ReviewPanel
        review={match.review!}
        left={market(match.left_id)}
        right={market(match.right_id)}
      />,
    );
    expect(screen.getByText("Rejected")).toBeVisible();
    expect(screen.getByText(/Intermeeting cut only/)).toBeVisible();
  });

  it("warns when the reviewed terms are no longer the published terms", () => {
    const match = matchNamed("match-cpi-2026-09");
    const left = market(match.left_id)!;
    render(
      <ReviewPanel
        review={match.review!}
        left={{ ...left, terms_hash: "f".repeat(64) }}
        right={market(match.right_id)}
      />,
    );
    expect(screen.getByText(/published terms changed on Kalshi/)).toBeVisible();
  });

  it("lists every reviewed settlement outcome", () => {
    const match = matchNamed("match-cpi-2026-09");
    render(<ReviewPanel review={match.review!} />);
    expect(screen.getByText("CPI above 3.0%")).toBeVisible();
    expect(screen.getByText("CPI at or below 3.0%")).toBeVisible();
  });

  it("shows each venue fee schedule with its evidence", () => {
    const match = matchNamed("match-cpi-2026-09");
    render(<ReviewPanel review={match.review!} />);
    expect(screen.getAllByText("$0.01")).toHaveLength(1);
    expect(screen.getAllByText("$0.02")).toHaveLength(1);
    expect(
      screen.getAllByText(/Published venue fee schedule reviewed/),
    ).toHaveLength(2);
  });
});

it("shows captured source text with its unresolved evidence gaps", async () => {
  const { SourceTerms } = await import("@/features/comparisons/source-terms");
  render(
    <SourceTerms
      market={{
        ...dataset.markets[0],
        settlement_details: {
          source_text_rulebook: "Captured cancellation terms.",
          source_issues: ["product_specification_applicability_unverified"],
        },
      }}
    />,
  );
  expect(
    screen.getByText("Settlement evidence remains incomplete"),
  ).toBeVisible();
  expect(
    screen.getByText("product specification applicability unverified"),
  ).toBeVisible();
  expect(screen.getByText("Captured rulebook text")).toBeVisible();
  expect(screen.getByText("Captured cancellation terms.")).toBeInTheDocument();
});
