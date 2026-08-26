import Image from "next/image";
import Link from "next/link";
import { ChevronsLeft, ChevronsRight, Settings, Sparkles } from "lucide-react";

import type { UserResponse } from "@/interface/auth";
import { ROUTE, Routes } from "@/variables/routes";

export function WorkspaceSidebar({
  user,
  collapsed,
  onToggle,
}: {
  user?: UserResponse;
  collapsed: boolean;
  onToggle: () => void;
}) {
  const visibleRoutes = Routes.filter((route) => user && route.roles.includes(user.role));
  const displayName = user?.email.split("@")[0] ?? "Workspace";
  const initial = displayName.charAt(0).toUpperCase();

  return (
    <aside
      className={`sticky top-0 hidden h-dvh shrink-0 flex-col border-r border-border bg-panel text-panel-foreground transition-[width] duration-200 lg:flex ${collapsed ? "w-20" : "w-64"}`}
    >
      <div
        className={`flex h-18.5 items-center border-b border-white/10 px-4 ${collapsed ? "justify-center" : "justify-between"}`}
      >
        {!collapsed && (
          <Link
            aria-label="Peka workspace home"
            className="flex items-center gap-2 text-xl font-bold tracking-tight"
            href={ROUTE.WORKSPACE}
          >
            <Image src="/peka.svg" alt="" aria-hidden="true" width={21} height={21} />
            peka
          </Link>
        )}
        <button
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className="rounded-md p-2 text-white/60 hover:bg-white/10 hover:text-white"
          onClick={onToggle}
        >
          {collapsed ? (
            <ChevronsRight aria-hidden="true" size={19} />
          ) : (
            <ChevronsLeft aria-hidden="true" size={19} />
          )}
        </button>
      </div>
      <nav aria-label="Workspace navigation" className="flex-1 space-y-1 overflow-y-auto px-3 py-5">
        <p
          className={`px-3 pb-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-white/45 ${collapsed ? "sr-only" : ""}`}
        >
          Workspace
        </p>
        {visibleRoutes.map(({ title, path, icon: Icon }) => (
          <Link
            key={path}
            title={collapsed ? title : undefined}
            className={`flex items-center gap-3 rounded-md px-3 py-2.5 text-sm text-white/65 transition-colors hover:bg-white/10 hover:text-white ${collapsed ? "justify-center" : ""}`}
            href={path}
          >
            <Icon aria-hidden="true" size={17} strokeWidth={1.8} />
            {!collapsed && title}
          </Link>
        ))}
      </nav>
      <div className="border-t border-white/10 p-3">
        <Link
          title={collapsed ? "Settings" : undefined}
          className={`flex items-center gap-3 rounded-md px-3 py-2.5 text-sm text-white/65 hover:bg-white/10 hover:text-white ${collapsed ? "justify-center" : ""}`}
          href={ROUTE.SETTINGS}
        >
          <Settings aria-hidden="true" size={17} strokeWidth={1.8} />
          {!collapsed && "Settings"}
        </Link>
        <div
          className={`mt-4 flex items-center gap-3 rounded-md bg-white/8 p-3 ${collapsed ? "justify-center" : ""}`}
        >
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
            {initial}
          </div>
          {!collapsed && (
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-white">{displayName}</p>
              <p className="truncate text-xs text-white/45">{user?.role ?? "Loading profile"}</p>
            </div>
          )}
          {!collapsed && <Sparkles aria-hidden="true" className="ml-auto text-primary" size={15} />}
        </div>
      </div>
    </aside>
  );
}
