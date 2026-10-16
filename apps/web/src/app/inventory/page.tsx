import { Suspense } from "react";
import { LoadingState } from "@/components/states";
import { InventoryBrowser } from "@/features/markets/inventory-browser";

export default function InventoryPage() {
  return (
    <Suspense fallback={<LoadingState label="Loading source inventory" />}>
      <InventoryBrowser />
    </Suspense>
  );
}
