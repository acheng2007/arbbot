import type { Metadata } from "next";
import { MatchList } from "@/features/comparisons/match-list";

export const metadata: Metadata = {
  title: "Contract comparisons",
  description:
    "Proposed contract pairs with side-by-side settlement terms and the evidence behind each match.",
};

export default function MatchesPage() {
  return (
    <div className="space-y-7">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
          Contract comparisons
        </h1>
        <p className="mt-3 max-w-2xl text-base leading-7 text-muted-foreground">
          Pairs proposed across venues, with the settlement fields that agree,
          differ, or remain unknown. Similar titles are not equivalence.
        </p>
      </header>
      <MatchList />
    </div>
  );
}
