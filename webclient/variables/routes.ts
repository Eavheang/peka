import type { LucideIcon } from "lucide-react";
import { Shield, SquarePen } from "lucide-react";

import type { UserRole } from "@/interface/auth";

export const ROUTE = {
  WORKSPACE: "/workspace",
  SETTINGS: "/workspace/settings",
  ADMIN: "/workspace/admin",
} as const;

export type WorkspaceRoute = {
  icon: LucideIcon;
  path: string;
  title: string;
  roles: UserRole[];
};

export const Routes: WorkspaceRoute[] = [
  {
    icon: SquarePen,
    path: ROUTE.WORKSPACE,
    title: "New chat",
    roles: ["admin", "senior", "staff"],
  },
  {
    icon: Shield,
    path: ROUTE.ADMIN,
    title: "Admin",
    roles: ["admin"],
  },
];
