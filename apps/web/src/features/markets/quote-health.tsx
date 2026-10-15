"use client";
import { MarketPrices } from "./market-prices";
import { ModeBadge } from "@/components/data-origin";
import { EmptyState } from "@/components/states";
import { Timestamp } from "@/components/timestamp";
import { QuoteAge } from "@/components/freshness";
import { formatPrice, formatQuantity } from "@/lib/decimal";
import type { Book, Level } from "@/lib/api/schema";

function LevelTable({ title, levels }: { title: string; levels: Level[] }) {
  return (
    <div>
      <h4 className="text-sm font-semibold">{title}</h4>
      {levels.length === 0 ? (
        <p className="mt-2 text-sm text-muted-foreground">
          No resting offers at any price.
        </p>
      ) : (
        <div
          className="mt-2 max-h-80 overflow-y-auto rounded-md border border-border px-3"
          tabIndex={0}
          aria-label={`${title} depth`}
        >
          <table className="w-full text-sm">
            <caption className="sr-only">{title} by price level</caption>
            <thead>
              <tr className="border-b border-border text-left text-muted-foreground">
                <th scope="col" className="py-2 font-medium">
                  Price
                </th>
                <th scope="col" className="py-2 text-right font-medium">
                  Size
                </th>
              </tr>
            </thead>
            <tbody>
              {levels.map((level) => (
                <tr
                  key={`${level.price}-${level.size}`}
                  className="border-b border-border/60"
                >
                  <td className="py-2 tabular-nums">
                    {formatPrice(level.price)}
                  </td>
                  <td className="py-2 text-right tabular-nums">
                    {formatQuantity(level.size)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

/**
 * Order-book health for one market. Source and receipt timestamps are shown
 * separately, because a venue that omits its own timestamp hides real latency.
 */
export function QuoteHealth({ book }: { book: Book }) {
  const empty = book.yes_asks.length === 0 && book.no_asks.length === 0;

  return (
    <section className="rounded-xl border border-border bg-card p-5 sm:p-6">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="mr-auto text-lg font-semibold">Quote health</h3>
        <ModeBadge mode={book.mode} feedOrigin={book.feed_origin} />
        <QuoteAge sourceAt={book.source_at} receivedAt={book.received_at} />
      </div>

      <div className="mt-4">
        <MarketPrices
          marketId={book.market_id}
          providedBook={book}
          shortNo={book.market_id.startsWith("polymarket_us:")}
        />
      </div>
      {empty && (
        <div className="mt-4">
          <EmptyState
            title="No executable depth"
            description="Neither side has resting offers. No executable estimate is available."
          />
        </div>
      )}
      <details className="mt-4">
        <summary className="cursor-pointer text-sm font-semibold">
          Order-book depth and diagnostics
        </summary>
        <p className="mt-3 text-sm text-muted-foreground">
          Refreshes every 5 seconds while this page is visible. Prices are
          resting offers per contract before fees; fills are not guaranteed.
        </p>

        {!book.source_at && (
          <p
            role="status"
            className="mt-4 rounded-md border border-amber-300 bg-amber-50 p-3.5 text-sm leading-6 text-amber-950"
          >
            This venue did not supply an exchange-side timestamp, so the age
            above is measured from when this system received the book. Real
            quote age may be greater.
          </p>
        )}

        {!empty && (
          <div className="mt-5 grid gap-6 sm:grid-cols-2">
            <LevelTable title="Yes asks" levels={book.yes_asks} />
            <LevelTable title="No asks" levels={book.no_asks} />
          </div>
        )}

        <dl className="mt-5 grid gap-3 border-t border-border pt-4 text-sm sm:grid-cols-3">
          <div>
            <dt className="text-muted-foreground">Minimum order size</dt>
            <dd className="mt-0.5 tabular-nums">
              {formatQuantity(book.min_order_size ?? "1")}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Exchange timestamp</dt>
            <dd className="mt-0.5">
              {book.source_at ? (
                <Timestamp value={book.source_at} />
              ) : (
                "not supplied"
              )}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Received</dt>
            <dd className="mt-0.5">
              <Timestamp value={book.received_at} />
            </dd>
          </div>
        </dl>
      </details>
    </section>
  );
}
