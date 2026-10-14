import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ClassificationPanel } from "@/features/comparisons/classification-panel";
import type { ClassificationSummary } from "@/lib/api/schema";

const advice: ClassificationSummary = {
  state: "fresh",
  supports_candidate: true,
  recorded: true,
  event: {
    choice: "same_event",
    confidence: 0.95,
    probabilities: { same_event: 0.9 },
  },
  clauses: {
    cancellation: {
      choice: "different_meaning",
      confidence: 0.91,
      probabilities: { different_meaning: 0.9 },
      evidence_ids: ["captured"],
    },
  },
  evidence: [
    {
      id: "captured",
      side: "left",
      clause: "cancellation",
      quotation: "Cancellation refunds all contracts.",
      start: 0,
      end: 34,
      applicability: "market_terms",
    },
  ],
  limitations: ["Applicable rulebook is missing."],
};

describe("advisory classification", () => {
  it("distinguishes model suggestions, scores and recorded responses from approval", () => {
    render(<ClassificationPanel advice={advice} />);
    expect(
      screen.getByRole("heading", { name: "AI suggests same event" }),
    ).toBeVisible();
    expect(screen.getByText(/not measured accuracy/)).toBeVisible();
    expect(screen.getByText(/Recorded model response/)).toBeVisible();
    expect(screen.queryByText("Verified in review")).not.toBeInTheDocument();
    expect(
      screen.getByText("Cancellation refunds all contracts."),
    ).toBeInTheDocument();
  });
  it.each([
    "pending",
    "stale",
    "unavailable",
    "unconfigured",
    "disabled",
  ] as const)("exposes %s without implying verification", (state) => {
    render(
      <ClassificationPanel
        advice={{ ...advice, state, supports_candidate: false }}
      />,
    );
    expect(
      screen.getByRole("heading", { name: `AI classification ${state}` }),
    ).toBeVisible();
    expect(
      screen.queryByRole("heading", { name: "AI suggests same event" }),
    ).not.toBeInTheDocument();
  });
  it("keeps legacy payloads readable", () => {
    render(<ClassificationPanel />);
    expect(
      screen.getByRole("heading", { name: "AI classification unconfigured" }),
    ).toBeVisible();
  });
});
