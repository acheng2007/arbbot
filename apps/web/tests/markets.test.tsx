import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { QuoteHealth } from "@/features/markets/quote-health";
import {
  applyLocalFilters,
  parseFilters,
  serializeFilters,
} from "@/features/markets/filters";
import { recordedDataset } from "@/lib/api/fixtures";

const dataset = recordedDataset(new Date("2026-09-21T06:00:00Z"));

describe("market filters", () => {
  it("round-trips through the address bar", () => {
    const filters = {
      view: "paired" as const,
      venue: "kalshi" as const,
      status: "open" as const,
      search: "cpi",
      offset: 50,
      category: "",
      relationship: "" as const,
    };
    expect(
      parseFilters(new URLSearchParams(serializeFilters(filters))),
    ).toEqual(filters);
  });

  it("drops values the API would reject", () => {
    const parsed = parseFilters(
      new URLSearchParams("venue=nasdaq&status=pending&offset=-3"),
    );
    expect(parsed).toEqual({
      view: "paired",
      venue: "",
      status: "",
      search: "",
      category: "",
      relationship: "" as const,
      offset: 0,
    });
  });

  it("matches on title and on the venue identifier", () => {
    expect(
      applyLocalFilters(dataset.markets, {
        view: "paired",
        venue: "",
        status: "",
        search: "0x8f21a4c7",
        offset: 0,
        category: "",
        relationship: "" as const,
      }).map((market) => market.id),
    ).toEqual(["polymarket:0x8f21"]);
  });

  it("narrows by status", () => {
    const closed = applyLocalFilters(dataset.markets, {
      view: "paired",
      venue: "",
      status: "closed",
      search: "",
      offset: 0,
      category: "",
      relationship: "" as const,
    });
    expect(closed).toHaveLength(1);
    expect(closed[0].status).toBe("closed");
  });
});

describe("quote health", () => {
  it("shows both sides of the book with exact prices and sizes", () => {
    render(<QuoteHealth book={dataset.books["kalshi:CPIYOY-26SEP-T3.0"]} />);
    fireEvent.click(screen.getByText("Order-book depth and diagnostics"));
    expect(screen.getByText("Yes asks")).toBeVisible();
    expect(screen.getByText("No asks")).toBeVisible();
    expect(screen.getByRole("cell", { name: "43\u00A2" })).toBeVisible();
    expect(screen.getByText("1,200")).toBeVisible();
  });

  it("warns when the venue supplied no exchange timestamp", () => {
    render(<QuoteHealth book={dataset.books["polymarket:0x8f21"]} />);
    fireEvent.click(screen.getByText("Order-book depth and diagnostics"));
    expect(
      screen.getByText(/did not supply an exchange-side timestamp/),
    ).toBeVisible();
    expect(screen.getByText("not supplied")).toBeVisible();
  });

  it("says there is no executable depth rather than showing an empty table", () => {
    render(<QuoteHealth book={dataset.books["kalshi:PAYROLLS-26OCT-T150"]} />);
    fireEvent.click(screen.getByText("Order-book depth and diagnostics"));
    expect(screen.getByText("No executable depth")).toBeVisible();
    expect(screen.queryByText("Yes asks")).toBeNull();
  });
});
