"use client";

import Image from "next/image";
import Link from "next/link";
import { useState } from "react";
import { ChevronsLeft, ChevronsRight, LogOut, Settings, Sparkles, X } from "lucide-react";
import { useRouter } from "next/navigation";

import Alertdialog from "@/components/Alertdialog";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Drawer, DrawerClose, DrawerContent, DrawerTitle } from "@/components/ui/drawer";
import type { UserResponse } from "@/interface/auth";
import { useLogout } from "@/services/auth";
import { clearAuthStorage, getStoredToken } from "@/utils/auth-storage";
import { ROUTE, Routes } from "@/variables/routes";

export function WorkspaceSidebar({
  user,
  collapsed,
  mobileOpen,
  onToggle,
  onMobileOpenChange,
}: {
  user?: UserResponse;
  collapsed: boolean;
  mobileOpen: boolean;
  onToggle: () => void;
  onMobileOpenChange: (open: boolean) => void;
}) {
  const router = useRouter();
  const logout = useLogout();
  const [logoutOpen, setLogoutOpen] = useState(false);
  const visibleRoutes = Routes.filter((route) => user && route.roles.includes(user.role));
  const displayName = user?.email.split("@")[0] ?? "Workspace";
  const initial = displayName.charAt(0).toUpperCase();

  function handleLogout() {
    const accessToken = getStoredToken("peka_access_token");
    if (!accessToken) {
      clearAuthStorage();
      router.replace("/sign-in");
      return;
    }

    logout.mutate(accessToken, {
      onSettled: () => {
        clearAuthStorage();
        router.replace("/sign-in");
      },
    });
  }

  return (
    <>
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
        <nav
          aria-label="Workspace navigation"
          className="flex-1 space-y-1 overflow-y-auto px-3 py-5"
        >
          <p
            className={`px-3 pb-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-white/45 ${collapsed ? "sr-only" : ""}`}
          >
            Workspace
          </p>
          {visibleRoutes.map(({ title, path, icon: Icon }) => {
            const link = (
              <Link
                aria-label={collapsed ? title : undefined}
                key={path}
                title={collapsed ? title : undefined}
                className={`flex items-center gap-3 rounded-md px-3 py-2.5 text-sm text-white/65 transition-colors hover:bg-white/10 hover:text-white ${collapsed ? "justify-center" : ""}`}
                href={path}
              >
                <Icon aria-hidden="true" size={17} strokeWidth={1.8} />
                {!collapsed && title}
              </Link>
            );

            return collapsed ? (
              <Tooltip key={path}>
                <TooltipTrigger render={link} />
                <TooltipContent side="right">{title}</TooltipContent>
              </Tooltip>
            ) : (
              link
            );
          })}
        </nav>
        <div className="border-t border-white/10 p-3">
          {collapsed ? (
            <Tooltip>
              <TooltipTrigger
                render={
                  <Link
                    aria-label="Settings"
                    className="flex items-center justify-center rounded-md p-2.5 text-white/65 hover:bg-white/10 hover:text-white"
                    href={ROUTE.SETTINGS}
                  />
                }
              >
                <Settings aria-hidden="true" size={17} strokeWidth={1.8} />
              </TooltipTrigger>
              <TooltipContent side="right">Settings</TooltipContent>
            </Tooltip>
          ) : (
            <Link
              className="flex items-center gap-3 rounded-md px-3 py-2.5 text-sm text-white/65 hover:bg-white/10 hover:text-white"
              href={ROUTE.SETTINGS}
            >
              <Settings aria-hidden="true" size={17} strokeWidth={1.8} />
              Settings
            </Link>
          )}
          {collapsed ? (
            <Tooltip>
              <TooltipTrigger
                render={
                  <button
                    aria-label="Log out"
                    className="mt-1 flex w-full items-center justify-center rounded-md p-2.5 text-white/65 hover:bg-white/10 hover:text-white"
                    type="button"
                    onClick={() => setLogoutOpen(true)}
                  />
                }
              >
                <LogOut aria-hidden="true" size={17} strokeWidth={1.8} />
              </TooltipTrigger>
              <TooltipContent side="right">Log out</TooltipContent>
            </Tooltip>
          ) : (
            <button
              className="mt-1 flex w-full items-center gap-3 rounded-md px-3 py-2.5 text-sm text-white/65 hover:bg-white/10 hover:text-white"
              type="button"
              onClick={() => setLogoutOpen(true)}
            >
              <LogOut aria-hidden="true" size={17} strokeWidth={1.8} />
              Log out
            </button>
          )}
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
            {!collapsed && (
              <Sparkles aria-hidden="true" className="ml-auto text-primary" size={15} />
            )}
          </div>
        </div>
      </aside>
      <Drawer swipeDirection="left" open={mobileOpen} onOpenChange={onMobileOpenChange}>
        <DrawerContent className="!bg-panel !text-panel-foreground w-[min(20rem,85vw)] max-w-[85vw] p-4">
          <div className="flex items-center justify-between border-b border-white/10 pb-4">
            <DrawerTitle className="flex items-center gap-2 text-xl tracking-tight text-panel-foreground">
              <Image src="/peka.svg" alt="" aria-hidden="true" width={21} height={21} />
              peka
            </DrawerTitle>
            <DrawerClose
              aria-label="Close workspace navigation"
              className="rounded-md p-2 hover:bg-white/10"
            >
              <X aria-hidden="true" size={18} />
            </DrawerClose>
          </div>
          <nav aria-label="Mobile workspace navigation" className="flex-1 py-5">
            <p className="px-3 pb-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-panel-foreground/60">
              Workspace
            </p>
            <div className="grid gap-1">
              {visibleRoutes.map(({ title, path, icon: Icon }) => (
                <Link
                  key={path}
                  className="flex items-center gap-3 rounded-md px-3 py-2.5 text-sm text-panel-foreground/75 hover:bg-white/10 hover:text-panel-foreground"
                  href={path}
                  onClick={() => onMobileOpenChange(false)}
                >
                  <Icon aria-hidden="true" size={17} strokeWidth={1.8} />
                  {title}
                </Link>
              ))}
            </div>
          </nav>
          <div className="border-t border-white/10 pt-3">
            <Link
              className="flex items-center gap-3 rounded-md px-3 py-2.5 text-sm text-panel-foreground/75 hover:bg-white/10 hover:text-panel-foreground"
              href={ROUTE.SETTINGS}
              onClick={() => onMobileOpenChange(false)}
            >
              <Settings aria-hidden="true" size={17} strokeWidth={1.8} />
              Settings
            </Link>
            <button
              className="mt-1 flex w-full items-center gap-3 rounded-md px-3 py-2.5 text-sm text-panel-foreground/75 hover:bg-white/10 hover:text-panel-foreground"
              type="button"
              onClick={() => {
                onMobileOpenChange(false);
                setLogoutOpen(true);
              }}
            >
              <LogOut aria-hidden="true" size={17} strokeWidth={1.8} />
              Log out
            </button>
          </div>
        </DrawerContent>
      </Drawer>
      <Alertdialog
        open={logoutOpen}
        onOpenChange={setLogoutOpen}
        title="Log out?"
        description="End your current workspace session?"
        confirmLabel="Log out"
        onConfirm={handleLogout}
        pending={logout.isPending}
      />
    </>
  );
}
