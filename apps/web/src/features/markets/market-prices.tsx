"use client";
import type { Book } from "@/lib/api/schema";
import { QuoteAge } from "@/components/freshness";
import { useApi } from "@/lib/query/hooks";
import { formatPrice, formatQuantity } from "@/lib/decimal";

export function MarketPrices({
  marketId,
  shortNo = false,
  providedBook,
}: {
  marketId: string;
  shortNo?: boolean;
  providedBook?: Book;
}) {
  return providedBook ? (
    <PriceDisplay quote={providedBook} shortNo={shortNo} />
  ) : (
    <QueriedPrices marketId={marketId} shortNo={shortNo} />
  );
}
function QueriedPrices({
  marketId,
  shortNo,
}: {
  marketId: string;
  shortNo: boolean;
}) {
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
  return <PriceDisplay quote={book.data.data} shortNo={shortNo} />;
}
function PriceDisplay({ quote, shortNo }: { quote: Book; shortNo: boolean }) {
  return (
    <div className="space-y-2">
      <dl className="grid grid-cols-2 gap-4">
        {[
          { label: "Yes ask", level: quote.yes_asks[0] },
          {
            label: shortNo ? "NO short collateral" : "No ask",
            level: quote.no_asks[0],
          },
        ].map(({ label, level }) => {
          return (
            <div key={label}>
              <dt className="text-xs text-muted-foreground">{label}</dt>
              <dd className="mt-1 text-2xl font-semibold tabular-nums text-primary">
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
      <QuoteAge
        sourceAt={quote.source_at}
        receivedAt={quote.received_at}
        compact
      />
    </div>
  );
}
