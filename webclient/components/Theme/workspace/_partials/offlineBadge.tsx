"use client";

import { WifiOff } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { useServerStatus } from "@/services/status";

export function OfflineBadge({ className }: { className?: string }) {
  if (!useServerStatus().offline) return null;

  return (
    <Badge role="status" className={className}>
      <WifiOff aria-hidden="true" size={12} />
      Offline
      <span className="sr-only">: web search, Google Drive and invitation email are paused.</span>
    </Badge>
  );
}
