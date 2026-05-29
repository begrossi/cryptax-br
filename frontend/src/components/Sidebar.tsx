"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, Wallet, RefreshCw, List,
  TrendingUp, FileText, Receipt, Globe, Shield,
} from "lucide-react";

const NAV = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/wallets", label: "Carteiras", icon: Wallet },
  { href: "/sync", label: "Sincronizar", icon: RefreshCw },
  { href: "/transactions", label: "Transações", icon: List },
  { divider: true, label: "Impostos" },
  { href: "/tax/gains", label: "Ganhos de Capital", icon: TrendingUp },
  { href: "/tax/darf", label: "DARF", icon: Receipt },
  { href: "/tax/irpf", label: "IRPF", icon: FileText },
  { href: "/tax/1888", label: "IN 1888", icon: Globe },
  { href: "/tax/coaf", label: "COAF", icon: Shield },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="w-56 shrink-0 bg-slate-900 text-slate-100 flex flex-col min-h-screen">
      <div className="p-4 border-b border-slate-700">
        <div className="font-bold text-lg tracking-tight">cryptax-br</div>
        <div className="text-xs text-slate-400 mt-0.5">Declaração de cripto 🇧🇷</div>
      </div>
      <nav className="flex-1 py-4 space-y-0.5 px-2">
        {NAV.map((item, i) =>
          "divider" in item ? (
            <div key={i} className="pt-4 pb-1 px-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">
              {item.label}
            </div>
          ) : (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors ${
                pathname === item.href
                  ? "bg-blue-600 text-white"
                  : "text-slate-300 hover:bg-slate-800 hover:text-white"
              }`}
            >
              <item.icon className="w-4 h-4 shrink-0" />
              {item.label}
            </Link>
          )
        )}
      </nav>
      <div className="p-4 border-t border-slate-700 text-xs text-slate-500">
        Open-source · local-first
      </div>
    </aside>
  );
}
