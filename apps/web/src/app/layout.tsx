import type { Metadata } from "next";
import Link from "next/link";
import { Navigation } from "@/components/navigation";
import { Providers } from "./providers";
import "./globals.css";
export const metadata: Metadata = {
  title: { default: "Arbbot | Research workspace", template: "%s | Arbbot" },
  description: "Prediction-market research and opportunity discovery.",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <a href="#main-content" className="skip-link">
            Skip to content
          </a>
          <div className="min-h-screen lg:grid lg:grid-cols-[240px_1fr]">
            <aside className="flex flex-col bg-sidebar px-5 py-6 text-white lg:min-h-screen lg:px-6 lg:py-9">
              <Link
                href="/"
                aria-label="Arbbot home"
                className="mb-7 flex items-center gap-3 text-xl font-bold tracking-tight"
              >
                <span
                  aria-hidden="true"
                  className="grid size-9 place-items-center rounded-lg bg-emerald-400 text-lg text-slate-950"
                >
                  a
                </span>
                arbbot<span className="text-emerald-400">.</span>
              </Link>
              <p className="mb-3 hidden px-3 text-[10px] font-semibold tracking-[0.18em] text-slate-400 lg:block">
                WORKSPACE
              </p>
              <Navigation />
              <div className="mt-auto hidden border-t border-white/10 pt-6 text-xs leading-5 text-slate-400 lg:block">
                <span className="mb-1 block font-medium text-slate-200">
                  Research before execution
                </span>
                Discovery and evaluation only.
                <br />
                No orders or fund transfers.
              </div>
            </aside>
            <div className="min-w-0">
              <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-card px-6 py-5 lg:px-12">
                <span className="text-sm text-muted-foreground">
                  Prediction-market research
                </span>
                <span className="rounded-full border border-border px-3 py-1 text-xs font-medium">
                  Estimates only, no execution
                </span>
              </header>
              <main
                id="main-content"
                tabIndex={-1}
                className="mx-auto max-w-6xl px-6 py-10 outline-none lg:px-12 lg:py-14"
              >
                {children}
              </main>
            </div>
          </div>
        </Providers>
      </body>
    </html>
  );
}
