import Link from "next/link";
import type { ReactNode } from "react";
import { DASHBOARD_NAV_ITEMS } from "@/config/navigation";

interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  return (
    <div className="flex min-h-screen">
      <aside className="w-64 border-r border-slate-200 bg-white p-5">
        <div className="mb-6">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">SER Dept</p>
          <p className="text-base font-semibold text-slate-900">Inventory System</p>
        </div>
        <nav aria-label="Main navigation" className="space-y-1">
          {DASHBOARD_NAV_ITEMS.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="block rounded-md px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 hover:text-slate-900"
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>
      <main className="flex-1 p-8">{children}</main>
    </div>
  );
}

