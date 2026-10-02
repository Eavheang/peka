import type { ReactNode } from "react";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { AUDIT_EVENT_TYPE_LABELS, type AuditEvent } from "@/interface/audit";
import { cn } from "@/lib/utils";

const COLUMNS = ["Type", "Created", "Actor", "Summary"] as const;
const SKELETON_ROWS = 5;
const SHIMMER_WIDTH = ["w-16", "w-36", "w-28", "max-w-xs w-full"] as const;

function formatCreatedAt(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function AuditTableFrame({ children }: { children: ReactNode }) {
  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-background shadow-sm">
      <Table>
        <TableHeader className="bg-secondary/70">
          <TableRow className="border-border hover:bg-secondary/70">
            {COLUMNS.map((column) => (
              <TableHead
                key={column}
                className="px-5 py-4 text-xs uppercase tracking-[0.14em] text-muted"
              >
                {column}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>{children}</TableBody>
      </Table>
    </div>
  );
}

export function AuditEventsSkeleton() {
  return (
    <div aria-busy="true" role="status">
      <span className="sr-only">Loading audit events...</span>
      <AuditTableFrame>
        {Array.from({ length: SKELETON_ROWS }, (_, row) => (
          <TableRow key={row} className="border-border hover:bg-transparent">
            {SHIMMER_WIDTH.map((width) => (
              <TableCell key={width} className="px-5 py-4">
                <span
                  aria-hidden="true"
                  className={cn(
                    "block h-4 animate-pulse rounded-md bg-muted motion-reduce:animate-none",
                    width,
                  )}
                />
              </TableCell>
            ))}
          </TableRow>
        ))}
      </AuditTableFrame>
    </div>
  );
}

export function AuditEventsEmpty() {
  return (
    <AuditTableFrame>
      <TableRow className="border-border hover:bg-transparent">
        <TableCell
          className="px-5 py-12 text-center text-sm whitespace-normal text-muted"
          colSpan={COLUMNS.length}
        >
          <p role="status">No audit events yet</p>
        </TableCell>
      </TableRow>
    </AuditTableFrame>
  );
}

export default function AuditEventsTable({ events }: { events: AuditEvent[] }) {
  return (
    <AuditTableFrame>
      {events.map((event) => (
        <TableRow key={event.id} className="border-border hover:bg-secondary/40">
          <TableCell className="px-5 py-4 font-medium text-foreground">
            {AUDIT_EVENT_TYPE_LABELS[event.type]}
          </TableCell>
          <TableCell className="px-5 py-4 text-foreground">
            <time dateTime={event.created_at}>{formatCreatedAt(event.created_at)}</time>
          </TableCell>
          <TableCell className="px-5 py-4 text-foreground">{event.actor_id ?? "\u2014"}</TableCell>
          <TableCell className="px-5 py-4 whitespace-normal text-foreground">
            {event.summary}
          </TableCell>
        </TableRow>
      ))}
    </AuditTableFrame>
  );
}
