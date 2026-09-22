import type { DecimalString } from "@/lib/api/schema";

type Parts = { sign: "" | "-"; whole: string; fraction: string };

/**
 * Splits an exact decimal string without converting it to a number. Returns
 * null when the value is not a plain decimal, so callers can show the raw text
 * instead of silently rendering something wrong.
 */
function parts(value: DecimalString): Parts | null {
  const match = /^([+-])?(\d*)(?:\.(\d*))?$/.exec(value.trim());
  if (!match) return null;
  const [, sign, whole = "", fraction = ""] = match;
  if (whole === "" && fraction === "") return null;
  return { sign: sign === "-" ? "-" : "", whole, fraction };
}

function assemble({ sign, whole, fraction }: Parts) {
  const integer = whole.replace(/^0+(?=\d)/, "") || "0";
  const trimmed = fraction.replace(/0+$/, "");
  const body = trimmed ? `${integer}.${trimmed}` : integer;
  return sign && body !== "0" ? `-${body}` : body;
}

/** Moves the decimal point right by `places`, exactly. */
export function shiftDecimal(value: DecimalString, places: number): string {
  const split = parts(value);
  if (!split) return value;
  const digits = `${split.whole}${split.fraction}`;
  const point = split.whole.length + places;
  if (point <= 0)
    return assemble({
      ...split,
      whole: "0",
      fraction: "0".repeat(-point) + digits,
    });
  if (point >= digits.length)
    return assemble({
      ...split,
      whole: digits + "0".repeat(point - digits.length),
      fraction: "",
    });
  return assemble({
    ...split,
    whole: digits.slice(0, point),
    fraction: digits.slice(point),
  });
}

/** True when the value is negative and non-zero. */
export function isNegative(value: DecimalString) {
  const split = parts(value);
  if (!split) return false;
  return split.sign === "-" && /[1-9]/.test(`${split.whole}${split.fraction}`);
}

const SYMBOLS: Record<string, string> = { USD: "$", USDC: "$" };

/**
 * Renders a monetary value with at least two decimal places, preserving every
 * supplied digit. Nothing is rounded away.
 */
export function formatMoney(value: DecimalString, asset = "USD") {
  const split = parts(value);
  if (!split) return value;
  const fraction = split.fraction.padEnd(2, "0");
  const integer = split.whole.replace(/^0+(?=\d)/, "") || "0";
  const grouped = integer.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const symbol = SYMBOLS[asset] ?? "";
  const body = `${symbol}${grouped}.${fraction}`;
  return split.sign ? `-${body}` : body;
}

/** Renders a ratio as an exact percentage, for example "0.0091" as "0.91%". */
export function formatPercent(value: DecimalString) {
  const shifted = shiftDecimal(value, 2);
  return shifted === value ? value : `${shifted}%`;
}

/** Renders a contract count, grouping thousands but keeping any fraction. */
export function formatQuantity(value: DecimalString) {
  const split = parts(value);
  if (!split) return value;
  const integer = (split.whole.replace(/^0+(?=\d)/, "") || "0").replace(
    /\B(?=(\d{3})+(?!\d))/g,
    ",",
  );
  const fraction = split.fraction.replace(/0+$/, "");
  return `${split.sign}${integer}${fraction ? `.${fraction}` : ""}`;
}

/** Renders a probability-style contract price, for example "0.43" as "43.0c". */
export function formatPrice(value: DecimalString) {
  const cents = shiftDecimal(value, 2);
  return cents === value ? value : `${cents}\u00A2`;
}
