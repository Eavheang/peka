"use client";

import { useEffect, useState } from "react";
import axios from "axios";
import { ArrowLeft } from "lucide-react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { AuditEventType } from "@/interface/audit";
import { useGetCurrentUser } from "@/services/auth";
import { useListAuditEvents } from "@/services/audit";
import { getStoredToken } from "@/utils/auth-storage";
import AuditEventsTable from "./_partials/auditEventsTable";

type AuditTypeFilter = "all" | AuditEventType;

const FILTERS: { value: AuditTypeFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "sync", label: "Sync" },
  { value: "query", label: "Query" },
  { value: "system", label: "System" },
];

function isAuditTypeFilter(value: unknown): value is AuditTypeFilter {
  return typeof value === "string" && FILTERS.some((filter) => filter.value === value);
}

function isForbidden(error: unknown) {
  return axios.isAxiosError(error) && error.response?.status === 403;
}

export default function AuditEventsPage() {
  const router = useRouter();
  const [token, setToken] = useState("");
  const [typeFilter, setTypeFilter] = useState<AuditTypeFilter>("all");
  const me = useGetCurrentUser(token);
  const eventsQuery = useListAuditEvents({
    type: typeFilter === "all" ? undefined : typeFilter,
    enabled: me.data?.role === "admin",
  });

  useEffect(() => setToken(getStoredToken("peka_access_token") ?? ""), []);
  useEffect(() => {
    if (me.data && me.data.role !== "admin") router.replace("/workspace");
  }, [me.data, router]);

  if (!me.data || me.data.role !== "admin") return null;

  const events = eventsQuery.data?.pages.flatMap((page) => page.items) ?? [];
  const forbidden = eventsQuery.isError && isForbidden(eventsQuery.error);
  const showInitialError = eventsQuery.isError && !eventsQuery.data && !forbidden;
  const showLoadMoreError = eventsQuery.isError && Boolean(eventsQuery.data) && !forbidden;

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

      <div className="flex items-center gap-3">
        <span id="audit-type-label" className="text-sm text-muted">
          Type
        </span>
        <Select
          value={typeFilter}
          onValueChange={(value) => {
            if (isAuditTypeFilter(value)) setTypeFilter(value);
          }}
        >
          <SelectTrigger aria-labelledby="audit-type-label" className="w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {FILTERS.map((filter) => (
              <SelectItem key={filter.value} value={filter.value}>
                {filter.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {eventsQuery.isLoading ? (
        <p className="text-sm text-muted" role="status">
          Loading audit events...
        </p>
      ) : forbidden ? null : showInitialError ? (
        <p className="text-sm text-danger" role="alert">
          Unable to load audit events.
        </p>
      ) : events.length === 0 ? (
        <p className="text-sm text-muted" role="status">
          No audit events yet
        </p>
      ) : (
        <>
          <AuditEventsTable events={events} />
          {showLoadMoreError && (
            <p className="text-sm text-danger" role="alert">
              Unable to load more audit events.
            </p>
          )}
          {eventsQuery.hasNextPage && (
            <Button
              className="border-border"
              disabled={eventsQuery.isFetchingNextPage}
              type="button"
              variant="outline"
              onClick={() => void eventsQuery.fetchNextPage()}
            >
              {eventsQuery.isFetchingNextPage ? "Loading..." : "Load more"}
            </Button>
          )}
        </>
      )}
    </section>
  );
}
