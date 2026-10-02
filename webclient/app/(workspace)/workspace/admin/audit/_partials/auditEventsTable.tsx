import type { AuditEvent, AuditEventType } from "@/interface/audit";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const TYPE_LABEL: Record<AuditEventType, string> = {
  sync: "Sync",
  query: "Query",
  system: "System",
};

function formatCreatedAt(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

type AuditEventsTableProps = {
  events: AuditEvent[];
};

export default function AuditEventsTable({ events }: AuditEventsTableProps) {
  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-background shadow-sm">
      <Table>
        <TableHeader className="bg-secondary/70">
          <TableRow className="border-border hover:bg-secondary/70">
            <TableHead className="px-5 py-4 text-xs uppercase tracking-[0.14em] text-muted">
              Type
            </TableHead>
            <TableHead className="px-5 py-4 text-xs uppercase tracking-[0.14em] text-muted">
              Created
            </TableHead>
            <TableHead className="px-5 py-4 text-xs uppercase tracking-[0.14em] text-muted">
              Actor
            </TableHead>
            <TableHead className="px-5 py-4 text-xs uppercase tracking-[0.14em] text-muted">
              Summary
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {events.map((event) => (
            <TableRow key={event.id} className="border-border hover:bg-secondary/40">
              <TableCell className="px-5 py-4 font-medium text-foreground">
                {TYPE_LABEL[event.type]}
              </TableCell>
              <TableCell className="px-5 py-4 text-foreground">
                <time dateTime={event.created_at}>{formatCreatedAt(event.created_at)}</time>
              </TableCell>
              <TableCell className="px-5 py-4 text-foreground">
                {event.actor_id ?? "\u2014"}
              </TableCell>
              <TableCell className="px-5 py-4 whitespace-normal text-foreground">
                {event.summary}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
