"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
export function Navigation() {
  const pathname = usePathname();
  return (
    <nav
      aria-label="Main navigation"
      className="flex items-center gap-6 sm:gap-8"
    >
      {[
        ["/markets", "Markets"],
        ["/opportunities", "Opportunities"],
        ["/matches", "Comparisons"],
      ].map(([href, label]) => (
        <Link
          key={href}
          href={href}
          aria-current={pathname.startsWith(href) ? "page" : undefined}
          className={cn(
            "border-b-2 border-transparent py-3 text-sm font-semibold text-muted-foreground transition-colors hover:text-foreground",
            pathname.startsWith(href) && "border-primary text-foreground",
          )}
        >
          {label}
        </Link>
      ))}
    </nav>
  );
}
