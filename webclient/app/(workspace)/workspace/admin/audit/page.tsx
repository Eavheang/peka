"use client";

import { useState } from "react";

import AuditEventsPanel from "./_partials/auditEventsPanel";
import AuditTypeFilter, { type AuditTypeFilterValue } from "./_partials/auditTypeFilter";

export default function AuditEventsPage() {
  const [typeFilter, setTypeFilter] = useState<AuditTypeFilterValue>("all");

  return (
    <section className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold">Audit log</h2>
          <p className="mt-1 text-sm text-muted">
            Sync, query, and system events, newest first.
          </p>
        </div>
        <AuditTypeFilter value={typeFilter} onChange={setTypeFilter} />
      </div>
      <AuditEventsPanel key={typeFilter} type={typeFilter === "all" ? undefined : typeFilter} />
    </section>
  );
}
