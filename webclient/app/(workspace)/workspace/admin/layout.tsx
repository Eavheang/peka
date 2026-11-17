"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { useGetCurrentUser } from "@/services/auth";
import { getStoredToken } from "@/utils/auth-storage";
import { ROUTE } from "@/variables/routes";

const TABS = [
  { href: ROUTE.ADMIN, label: "Users" },
  { href: ROUTE.ADMIN_SETTINGS, label: "Workspace settings" },
  { href: ROUTE.ADMIN_AUDIT, label: "Audit log" },
] as const;

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [token, setToken] = useState("");
  const me = useGetCurrentUser(token);

  useEffect(() => setToken(getStoredToken("peka_access_token") ?? ""), []);
  useEffect(() => {
    if (me.data && me.data.role !== "admin") router.replace(ROUTE.WORKSPACE);
  }, [me.data, router]);

  if (!me.data || me.data.role !== "admin") return null;

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-8 p-6 lg:p-10">
      <header className="flex flex-col gap-5 border-b border-border">
        <div>
          <h1 className="text-2xl font-semibold">Admin</h1>
          <p className="mt-1 text-sm text-muted">
            Manage who can use PEKA, the services it connects to, and what has happened.
          </p>
        </div>
        <nav aria-label="Admin sections" className="-mb-px flex gap-6 overflow-x-auto">
          {TABS.map((tab) => {
            const active = pathname === tab.href;
            return (
              <Link
                key={tab.href}
                href={tab.href}
                aria-current={active ? "page" : undefined}
                className={`shrink-0 border-b-2 pb-3 text-sm font-medium transition-colors ${
                  active
                    ? "border-primary text-foreground"
                    : "border-transparent text-muted hover:border-border hover:text-foreground"
                }`}
              >
                {tab.label}
              </Link>
            );
          })}
        </nav>
      </header>
      {children}
    </div>
  );
}
