"use client";
import { QuoteAge } from "@/components/freshness";
import { useApi } from "@/lib/query/hooks";
import { formatPrice, formatQuantity } from "@/lib/decimal";

export function MarketPrices({ marketId }: { marketId: string }) {
  const book = useApi(
    "book",
    { params: { market_id: marketId } },
    {
      refetchInterval: 5000,
    },
  );
  if (book.isPending)
    return (
      <p className="mt-4 text-sm text-muted-foreground">Loading prices...</p>
    );
  if (book.isError || !book.data)
    return (
      <p className="mt-4 text-sm text-muted-foreground">
        Prices unavailable. Open market for details.
      </p>
    );
  const quote = book.data.data;
  return (
    <div className="mt-4 space-y-3 border-t border-border pt-3">
      <dl className="grid grid-cols-2 gap-4">
        {[
          { label: "Yes ask", level: quote.yes_asks[0] },
          { label: "No ask", level: quote.no_asks[0] },
        ].map(({ label, level }) => {
          return (
            <div key={label}>
              <dt className="text-xs text-muted-foreground">{label}</dt>
              <dd className="mt-1 text-lg font-semibold tabular-nums">
                {level ? formatPrice(level.price) : "No offers"}
              </dd>
              {level && (
                <dd className="text-xs text-muted-foreground">
                  {formatQuantity(level.size)} contracts at this price
                </dd>
              )}
            </div>
          );
        })}
      </dl>
      <QuoteAge sourceAt={quote.source_at} receivedAt={quote.received_at} />
    </div>
  );
}
