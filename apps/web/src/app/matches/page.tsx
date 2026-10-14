import type { Metadata } from "next";
import { MatchList } from "@/features/comparisons/match-list";

export const metadata: Metadata = {
  title: "Contract comparisons",
  description:
    "Proposed contract pairs with side-by-side settlement terms and the evidence behind each match.",
};

export default function MatchesPage() {
  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
          Contract comparisons
        </h1>
      </header>
      <MatchList />
    </div>
  );
}
