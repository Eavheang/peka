"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import type { AuditEventType } from "@/interface/audit";
import { isAuditEventsForbidden, useListAuditEvents } from "@/services/audit";
import AuditEventsSkeleton from "./auditEventsSkeleton";
import AuditEventsTable from "./auditEventsTable";

export default function AuditEventsPanel({ type }: { type?: AuditEventType }) {
  const eventsQuery = useListAuditEvents({ type });
  const [page, setPage] = useState(0);
  const pages = eventsQuery.data?.pages ?? [];
  const events = pages[page]?.items ?? [];
  const hasNext = page + 1 < pages.length || eventsQuery.hasNextPage;
  const showSkeleton = eventsQuery.isPending || (eventsQuery.isFetching && !eventsQuery.data);

  if (showSkeleton) return <AuditEventsSkeleton />;
  if (isAuditEventsForbidden(eventsQuery.error)) return null;

  if (eventsQuery.isError && !eventsQuery.data) {
    return (
      <p className="text-sm text-danger" role="alert">
        Unable to load audit events.
      </p>
    );
  }

  const goNext = async () => {
    if (page + 1 >= pages.length) {
      const result = await eventsQuery.fetchNextPage();
      if (result.isError) return;
    }
    setPage((value) => value + 1);
  };

  return (
    <div className="flex flex-col gap-4">
      <AuditEventsTable events={events} />
      {eventsQuery.isError && (
        <p className="text-sm text-danger" role="alert">
          Unable to load more audit events.
        </p>
      )}
      {(page > 0 || hasNext) && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted">Page {page + 1}</p>
          <div className="flex gap-2">
            <Button
              className="border-border"
              disabled={page === 0}
              type="button"
              variant="outline"
              onClick={() => setPage((value) => value - 1)}
            >
              Previous
            </Button>
            <Button
              className="border-border"
              disabled={!hasNext || eventsQuery.isFetchingNextPage}
              type="button"
              variant="outline"
              onClick={() => void goNext()}
            >
              {eventsQuery.isFetchingNextPage ? "Loading..." : "Next"}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
