import { TableCell, TableRow } from "@/components/ui/table";
import { AUDIT_EVENT_TYPE_LABELS, type AuditEvent } from "@/interface/audit";
import AuditTableFrame, { AUDIT_TABLE_COLUMNS } from "./auditTableFrame";

export default function AuditEventsTable({ events }: { events: AuditEvent[] }) {
  return (
    <AuditTableFrame>
      {events.length === 0 && (
        <TableRow className="border-border hover:bg-transparent">
          <TableCell
            className="px-5 py-12 text-center text-sm whitespace-normal text-muted"
            colSpan={AUDIT_TABLE_COLUMNS.length}
          >
            No audit events yet
          </TableCell>
        </TableRow>
      )}
      {events.map((event) => (
        <TableRow key={event.id} className="border-border hover:bg-secondary/40">
          <TableCell className="px-5 py-4 font-medium text-foreground">
            {AUDIT_EVENT_TYPE_LABELS[event.type]}
          </TableCell>
          <TableCell className="px-5 py-4 text-foreground">
            <time dateTime={event.created_at}>
              {new Date(event.created_at).toLocaleString(undefined, {
                dateStyle: "medium",
                timeStyle: "short",
              })}
            </time>
          </TableCell>
          <TableCell className="px-5 py-4 text-foreground">{event.actor_id ?? "—"}</TableCell>
          <TableCell className="px-5 py-4 whitespace-normal text-foreground">
            {event.summary}
          </TableCell>
        </TableRow>
      ))}
    </AuditTableFrame>
  );
}
