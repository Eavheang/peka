"use client";

import { Button } from "@/components/ui/button";
import type { AuditEventType } from "@/interface/audit";
import { isAuditEventsForbidden, useListAuditEvents } from "@/services/audit";
import AuditEventsSkeleton from "./auditEventsSkeleton";
import AuditEventsTable from "./auditEventsTable";

export default function AuditEventsPanel({ type }: { type?: AuditEventType }) {
  const eventsQuery = useListAuditEvents({ type });
  const events = eventsQuery.data?.pages.flatMap((page) => page.items) ?? [];
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

  return (
    <div className="flex flex-col gap-4">
      <AuditEventsTable events={events} />
      {eventsQuery.isError && (
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
    </div>
  );
}
