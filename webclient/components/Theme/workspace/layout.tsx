"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { Menu } from "lucide-react";
import { useRouter } from "next/navigation";

import type { UserResponse } from "@/interface/auth";
import { clearAuthStorage, getStoredToken } from "@/utils/auth-storage";
import { useGetCurrentUser } from "@/services/auth";

import { WorkspaceSidebar } from "./Sidebar";

export default function WorkspaceLayout({ children }: Readonly<{ children: ReactNode }>) {
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [accessToken, setAccessToken] = useState("");

  useEffect(() => {
    setAccessToken(getStoredToken("peka_access_token") ?? "");
  }, []);

  const userQuery = useGetCurrentUser(accessToken);

  useEffect(() => {
    if (!userQuery.isError) return;
    clearAuthStorage();
    router.replace("/sign-in");
  }, [router, userQuery.isError]);

  const user: UserResponse | undefined = userQuery.data;

  return (
    <div className="flex h-dvh overflow-hidden bg-background text-foreground">
      <WorkspaceSidebar
        collapsed={collapsed}
        mobileOpen={mobileOpen}
        onMobileOpenChange={setMobileOpen}
        onToggle={() => setCollapsed((value) => !value)}
        user={user}
      />
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <header className="flex h-16 items-center border-b border-border px-4 lg:hidden">
          <button
            aria-label="Open workspace navigation"
            className="rounded-md p-2 text-muted hover:bg-secondary hover:text-foreground"
            type="button"
            onClick={() => setMobileOpen(true)}
          >
            <Menu aria-hidden="true" size={20} />
          </button>
        </header>
        <main className="min-h-0 min-w-0 flex-1 overflow-y-auto">{children}</main>
      </div>
    </div>
  );
}
