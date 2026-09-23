import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CostBreakdown } from "@/features/opportunities/cost-breakdown";
import { StreamStatusBanner } from "@/features/opportunities/stream-status";
import { recordedDataset } from "@/lib/api/fixtures";

const dataset = recordedDataset(new Date("2026-09-21T06:00:00Z"));
const [opportunity] = dataset.opportunities;

describe("cost breakdown", () => {
  it("shows fees, depth cost, and slippage allowance separately", () => {
    render(<CostBreakdown opportunity={opportunity} />);
    expect(screen.getByText("Executable depth cost")).toBeVisible();
    expect(screen.getByText("$240.00")).toBeVisible();
    expect(screen.getByText("Fees")).toBeVisible();
    expect(screen.getByText("$7.50")).toBeVisible();
    expect(screen.getByText("Slippage allowance")).toBeVisible();
    expect(screen.getByText("$0.24")).toBeVisible();
  });

  it("states the net result as being after all costs", () => {
    render(<CostBreakdown opportunity={opportunity} />);
    expect(screen.getByText("Net profit after all costs")).toBeVisible();
    expect(screen.getByText("$2.26")).toBeVisible();
  });

  it("reports a negative result as a loss", () => {
    render(
      <CostBreakdown opportunity={{ ...opportunity, net_profit: "-3.40" }} />,
    );
    expect(screen.getByText("Net loss after all costs")).toBeVisible();
    expect(screen.getByText("-$3.40")).toBeVisible();
  });

  it("says when the backend supplied no outlay rather than computing one", () => {
    render(
      <CostBreakdown
        opportunity={{ ...opportunity, estimated_outlay: null }}
      />,
    );
    expect(screen.getByText("not supplied")).toBeVisible();
  });

  it("renders the exact decimals it was given", () => {
    render(
      <CostBreakdown
        opportunity={{
          ...opportunity,
          net_profit: "0.30000000000000004",
          return_on_capital: "0.00913333",
        }}
      />,
    );
    expect(screen.getByText("$0.30000000000000004")).toBeVisible();
    expect(screen.getByText(/0\.913333%/)).toBeVisible();
  });
});

describe("live update status", () => {
  it("confirms the connection when the stream is open", () => {
    render(
      <StreamStatusBanner
        state={{ status: "open", lastEventAt: Date.now(), drops: 0 }}
      />,
    );
    expect(screen.getByText("Live updates connected")).toBeVisible();
  });

  it("marks the figures as unconfirmed while reconnecting", () => {
    render(
      <StreamStatusBanner
        state={{ status: "reconnecting", lastEventAt: Date.now(), drops: 2 }}
      />,
    );
    const banner = screen.getByRole("status");
    expect(banner).toHaveTextContent("Live updates disconnected, retrying.");
    expect(banner).toHaveTextContent(/may no longer hold/);
    expect(banner).toHaveTextContent("dropped 2 times");
  });

  it("does not imply confirmation before the first event", () => {
    render(
      <StreamStatusBanner
        state={{ status: "connecting", lastEventAt: null, drops: 0 }}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      /Nothing below has been confirmed by a live update yet/,
    );
  });
});
