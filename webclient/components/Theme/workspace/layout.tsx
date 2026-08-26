"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import type { UserResponse } from "@/interface/auth";
import { useGetCurrentUser } from "@/services/auth";

import { WorkspaceSidebar } from "./Sidebar";

export default function WorkspaceLayout({ children }: Readonly<{ children: ReactNode }>) {
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const [accessToken, setAccessToken] = useState("");

  useEffect(() => {
    setAccessToken(sessionStorage.getItem("peka_access_token") ?? "");
  }, []);

  const userQuery = useGetCurrentUser(accessToken);

  useEffect(() => {
    if (!userQuery.isError) return;
    sessionStorage.removeItem("peka_access_token");
    sessionStorage.removeItem("peka_refresh_token");
    document.cookie = "peka_access_token=; Max-Age=0; Path=/; SameSite=Lax";
    router.replace("/sign-in");
  }, [router, userQuery.isError]);

  const user: UserResponse | undefined = userQuery.data;

  return (
    <div className="flex h-dvh overflow-hidden bg-background text-foreground">
      <WorkspaceSidebar
        collapsed={collapsed}
        onToggle={() => setCollapsed((value) => !value)}
        user={user}
      />
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <main className="min-h-0 min-w-0 flex-1 overflow-y-auto">{children}</main>
      </div>
    </div>
  );
}
