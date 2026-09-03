"use client";

import Link from "next/link";
import { useState } from "react";
import { ChevronRight, LogOut, Settings } from "lucide-react";

import {
  Popover,
  PopoverPortal,
  PopoverPopup,
  PopoverPositioner,
  PopoverTrigger,
} from "@/components/ui/popover";
import { ROUTE } from "@/variables/routes";

export function ProfileMenu({
  collapsed,
  displayName,
  initial,
  onLogout,
  onNavigate,
  role,
}: {
  collapsed?: boolean;
  displayName: string;
  initial: string;
  onLogout: () => void;
  onNavigate?: () => void;
  role?: string;
}) {
  const [open, setOpen] = useState(false);

  function handleNavigate() {
    setOpen(false);
    onNavigate?.();
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        aria-label="Open profile menu"
        className={`group flex w-full items-center gap-3 rounded-md bg-white/8 p-3 text-left transition-colors hover:bg-white/12 ${collapsed ? "justify-center" : ""}`}
        type="button"
      >
        <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
          {initial}
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-white">{displayName}</p>
            <p className="truncate text-xs capitalize text-white/45">{role ?? "Loading profile"}</p>
          </div>
        )}
        {!collapsed && (
          <ChevronRight
            aria-hidden="true"
            className="ml-auto shrink-0 text-white/50 transition-transform group-data-popup-open:translate-x-0.5"
            size={16}
          />
        )}
      </PopoverTrigger>
      <PopoverPortal>
        <PopoverPositioner
          align="start"
          alignOffset={-4}
          collisionPadding={8}
          side="top"
          sideOffset={8}
        >
          <PopoverPopup className="w-60 rounded-2xl bg-panel-elevated p-3 text-panel-foreground shadow-2xl ring-1 ring-white/10">
            <div className="grid gap-1">
              <Link
                className="flex items-center gap-3 rounded-md px-2 py-2 text-sm text-white/75 transition-colors hover:bg-white/10 hover:text-white"
                href={ROUTE.SETTINGS}
                onClick={handleNavigate}
              >
                <Settings aria-hidden="true" size={17} strokeWidth={1.8} />
                Settings
              </Link>
              <button
                className="flex w-full items-center gap-3 rounded-md px-2 py-2 text-sm text-white/75 transition-colors hover:bg-white/10 hover:text-white"
                type="button"
                onClick={() => {
                  setOpen(false);
                  onLogout();
                }}
              >
                <LogOut aria-hidden="true" size={17} strokeWidth={1.8} />
                Log out
              </button>
            </div>
          </PopoverPopup>
        </PopoverPositioner>
      </PopoverPortal>
    </Popover>
  );
}
