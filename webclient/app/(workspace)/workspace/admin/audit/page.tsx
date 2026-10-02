"use client";

import { useEffect, useState } from "react";
import { ArrowLeft } from "lucide-react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { useGetCurrentUser } from "@/services/auth";
import { getStoredToken } from "@/utils/auth-storage";
import AuditEventsPanel from "./_partials/auditEventsPanel";
import AuditTypeFilter, { type AuditTypeFilterValue } from "./_partials/auditTypeFilter";

export default function AuditEventsPage() {
  const router = useRouter();
  const [token, setToken] = useState("");
  const [typeFilter, setTypeFilter] = useState<AuditTypeFilterValue>("all");
  const me = useGetCurrentUser(token);

  useEffect(() => setToken(getStoredToken("peka_access_token") ?? ""), []);
  useEffect(() => {
    if (me.data && me.data.role !== "admin") router.replace("/workspace");
  }, [me.data, router]);

  if (!me.data || me.data.role !== "admin") return null;

  return (
    <section className="mx-auto max-w-5xl space-y-8 p-6 lg:p-10">
      <div>
        <Button
          className="border-border"
          type="button"
          variant="outline"
          onClick={() => router.push("/workspace/admin")}
        >
          <ArrowLeft aria-hidden="true" />
          Back
        </Button>
        <h1 className="mt-3 text-2xl font-semibold">Audit events</h1>
        <p className="mt-1 text-sm text-muted">Review sync, query, and system activity.</p>
      </div>
      <AuditTypeFilter value={typeFilter} onChange={setTypeFilter} />
      <AuditEventsPanel type={typeFilter === "all" ? undefined : typeFilter} />
    </section>
  );
}
