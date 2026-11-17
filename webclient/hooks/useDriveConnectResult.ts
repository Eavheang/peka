"use client";

import { useEffect } from "react";

import { toast } from "@/components/ui/toast";

// Google consent redirects back with `?google_drive=connected|error`: say how it went, then drop the parameter.
export function useDriveConnectResult(successTitle: string) {
  useEffect(() => {
    const url = new URL(window.location.href);
    const result = url.searchParams.get("google_drive");
    if (!result) return;
    toast.add(
      result === "connected"
        ? { title: successTitle, type: "success" }
        : { title: "Google Drive could not be connected. Please try again.", type: "error" },
    );
    url.searchParams.delete("google_drive");
    window.history.replaceState(null, "", url);
  }, [successTitle]);
}
