"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, ArrowUpRight, LayoutDashboard } from "lucide-react";
import { cn } from "@/lib/utils";
export function Navigation() {
  const pathname = usePathname();
  return (
    <nav aria-label="Main navigation" className="flex gap-2 lg:flex-col">
      {[
        { href: "/", label: "Overview", icon: LayoutDashboard },
        { href: "/connection", label: "API connection", icon: Activity },
      ].map(({ href, label, icon: Icon }) => (
        <Link
          key={href}
          href={href}
          aria-current={pathname === href ? "page" : undefined}
          className={cn(
            "flex items-center gap-3 rounded-md px-3 py-3 text-sm font-medium text-slate-300 hover:bg-white/10 hover:text-white",
            pathname === href && "bg-white/10 text-white",
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
