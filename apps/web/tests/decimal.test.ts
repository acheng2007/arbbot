import { describe, expect, it } from "vitest";
import {
  formatMoney,
  formatPercent,
  formatPrice,
  formatQuantity,
  isNegative,
  shiftDecimal,
} from "@/lib/decimal";

describe("exact decimal rendering", () => {
  it("keeps digits that binary floating point would lose", () => {
    // 0.1 + 0.2 is the canonical float failure; these strings must survive intact.
    expect(formatMoney("0.30000000000000004")).toBe("$0.30000000000000004");
    expect(formatMoney("12345678901234567890.01")).toBe(
      "$12,345,678,901,234,567,890.01",
    );
    expect(formatQuantity("9007199254740993")).toBe("9,007,199,254,740,993");
  });

  it("pads money to two places without rounding anything away", () => {
    expect(formatMoney("2.2")).toBe("$2.20");
    expect(formatMoney("2")).toBe("$2.00");
    expect(formatMoney("2.256")).toBe("$2.256");
    expect(formatMoney("-0.5")).toBe("-$0.50");
  });

  it("shifts the decimal point exactly in both directions", () => {
    expect(shiftDecimal("0.0091", 2)).toBe("0.91");
    expect(shiftDecimal("0.43", 2)).toBe("43");
    expect(shiftDecimal("1", 2)).toBe("100");
    expect(shiftDecimal("0.000001", 2)).toBe("0.0001");
    expect(shiftDecimal("123.456", 2)).toBe("12345.6");
  });

  it("renders ratios and prices from the shifted value", () => {
    expect(formatPercent("0.0091")).toBe("0.91%");
    expect(formatPrice("0.43")).toBe("43\u00A2");
    expect(formatPrice("0.055")).toBe("5.5\u00A2");
  });

  it("identifies a negative result but not a signed zero", () => {
    expect(isNegative("-1.50")).toBe(true);
    expect(isNegative("-0.00")).toBe(false);
    expect(isNegative("0.01")).toBe(false);
  });

  it("returns unparseable values untouched rather than guessing", () => {
    expect(formatMoney("not a number")).toBe("not a number");
    expect(formatQuantity("")).toBe("");
    expect(shiftDecimal("1e5", 2)).toBe("1e5");
  });
});
