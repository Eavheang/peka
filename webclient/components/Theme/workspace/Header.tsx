import Link from "next/link";
import { Bell, ChevronDown, Menu, Search } from "lucide-react";

import type { UserResponse } from "@/interface/auth";
import { ROUTE } from "@/variables/routes";

export function WorkspaceHeader({ user }: { user?: UserResponse }) {
  const displayName = user?.email.split("@")[0] ?? "Workspace";
  const initial = displayName.charAt(0).toUpperCase();

  return (
    <header className="sticky top-0 z-40 flex h-18.5 items-center justify-between border-b border-border bg-background/95 px-4 backdrop-blur sm:px-6">
      <div className="flex items-center gap-3">
        <button
          aria-label="Open workspace navigation"
          className="rounded-md p-2 text-muted hover:bg-secondary hover:text-foreground lg:hidden"
        >
          <Menu aria-hidden="true" size={20} />
        </button>
        <div className="hidden items-center gap-2 text-sm text-muted sm:flex">
          <span>Workspace</span>
          <span className="text-border">/</span>
          <span className="font-medium text-foreground">Overview</span>
        </div>
      </div>
      <div className="flex items-center gap-1 sm:gap-3">
        <button
          aria-label="Search workspace"
          className="rounded-md p-2 text-muted hover:bg-secondary hover:text-foreground"
        >
          <Search aria-hidden="true" size={19} />
        </button>
        <button
          aria-label="View notifications"
          className="rounded-md p-2 text-muted hover:bg-secondary hover:text-foreground"
        >
          <Bell aria-hidden="true" size={19} />
        </button>
        <Link
          className="ml-1 flex items-center gap-2 rounded-md p-1.5 pr-2 hover:bg-secondary"
          href={ROUTE.SETTINGS}
        >
          <span className="flex size-8 items-center justify-center rounded-full bg-panel text-sm font-semibold text-panel-foreground">
            {initial}
          </span>
          <span className="hidden text-sm font-medium sm:inline">{displayName}</span>
          <ChevronDown aria-hidden="true" className="hidden text-muted sm:inline" size={15} />
        </Link>
      </div>
    </header>
  );
}
