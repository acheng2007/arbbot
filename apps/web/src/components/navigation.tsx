"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  ArrowUpRight,
  ChartNoAxesCombined,
  Files,
  GitCompareArrows,
  LayoutDashboard,
} from "lucide-react";
import { cn } from "@/lib/utils";
export function Navigation() {
  const pathname = usePathname();
  const isCurrent = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);
  return (
    <nav
      aria-label="Main navigation"
      className="flex gap-2 overflow-x-auto lg:flex-col lg:overflow-visible"
    >
      {[
        { href: "/", label: "Overview", icon: LayoutDashboard },
        {
          href: "/opportunities",
          label: "Opportunities",
          icon: ChartNoAxesCombined,
        },
        { href: "/matches", label: "Comparisons", icon: GitCompareArrows },
        { href: "/markets", label: "Markets", icon: Files },
        { href: "/connection", label: "API connection", icon: Activity },
      ].map(({ href, label, icon: Icon }) => (
        <Link
          key={href}
          href={href}
          aria-current={isCurrent(href) ? "page" : undefined}
          className={cn(
            "flex shrink-0 items-center gap-3 rounded-md px-3 py-3 text-sm font-medium whitespace-nowrap text-slate-300 hover:bg-white/10 hover:text-white",
            isCurrent(href) && "bg-white/10 text-white",
          )}
        >
          <Icon aria-hidden="true" className="size-4" />
          {label}
          <ArrowUpRight
            aria-hidden="true"
            className="ml-auto hidden size-3 opacity-50 lg:block"
          />
        </Link>
      ))}
    </nav>
  );
}
