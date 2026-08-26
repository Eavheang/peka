import type { LucideIcon } from "lucide-react";
import { Files, FolderKanban, LayoutDashboard, Settings } from "lucide-react";

import type { UserRole } from "@/interface/auth";

export const ROUTE = {
  WORKSPACE: "/workspace",
  DOCUMENTS: "/workspace/documents",
  PROJECTS: "/workspace/projects",
  SETTINGS: "/workspace/settings",
} as const;

export type WorkspaceRoute = {
  icon: LucideIcon;
  path: string;
  title: string;
  roles: UserRole[];
};

export const Routes: WorkspaceRoute[] = [
  {
    icon: LayoutDashboard,
    path: ROUTE.WORKSPACE,
    title: "Overview",
    roles: ["admin", "senior", "staff"],
  },
  { icon: Files, path: ROUTE.DOCUMENTS, title: "Documents", roles: ["admin", "senior", "staff"] },
  {
    icon: FolderKanban,
    path: ROUTE.PROJECTS,
    title: "Projects",
    roles: ["admin", "senior", "staff"],
  },
];

export const ProxyProtectedRoutes: WorkspaceRoute[] = [
  ...Routes,
  { icon: Settings, path: ROUTE.SETTINGS, title: "Settings", roles: ["admin", "senior", "staff"] },
];

export function resolveRouteForPathname(pathname: string) {
  return Routes.filter(
    (route) => pathname === route.path || pathname.startsWith(`${route.path}/`),
  ).sort((a, b) => b.path.length - a.path.length)[0];
}
