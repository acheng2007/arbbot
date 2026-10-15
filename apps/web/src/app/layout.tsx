import type { Metadata } from "next";
import Link from "next/link";
import { Activity } from "lucide-react";
import { Navigation } from "@/components/navigation";
import { Providers } from "./providers";
import "./globals.css";
export const metadata: Metadata = {
  title: { default: "Arbbot | Markets", template: "%s | Arbbot" },
  description: "Cross-exchange prediction markets and opportunity discovery.",
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
          <header className="border-b border-border bg-card">
            <div className="mx-auto flex max-w-[1280px] flex-wrap items-center justify-between gap-x-10 px-4 sm:px-8">
              <Link
                href="/markets"
                aria-label="Arbbot home"
                className="py-3 text-2xl font-bold tracking-tight text-primary"
              >
                arbbot<span className="text-foreground">.</span>
              </Link>
              <div className="order-3 w-full sm:order-none sm:w-auto sm:flex-1">
                <Navigation />
              </div>
              <Link
                href="/connection"
                aria-label="Connection status"
                className="flex items-center gap-2 rounded-full border border-border px-3 py-2 text-xs text-muted-foreground hover:text-foreground"
              >
                <Activity className="size-4" aria-hidden="true" />
                <span className="hidden sm:inline">Connection</span>
              </Link>
            </div>
          </header>
          <main
            id="main-content"
            tabIndex={-1}
            className="mx-auto max-w-[1280px] px-4 py-4 outline-none sm:px-8 sm:py-8"
          >
            {children}
          </main>
        </Providers>
      </body>
    </html>
  );
}
