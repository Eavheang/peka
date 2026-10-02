import { TableCell, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import AuditTableFrame, { AUDIT_TABLE_COLUMNS } from "./auditTableFrame";

const SKELETON_ROWS = 5;
const SHIMMER_WIDTH = ["w-16", "w-36", "w-28", "max-w-xs w-full"] as const;

export default function AuditEventsSkeleton() {
  return (
    <div aria-busy="true" role="status">
      <span className="sr-only">Loading audit events</span>
      <AuditTableFrame>
        {Array.from({ length: SKELETON_ROWS }, (_, row) => (
          <TableRow key={row} className="border-border hover:bg-transparent">
            {AUDIT_TABLE_COLUMNS.map((column, index) => (
              <TableCell key={column} className="px-5 py-4">
                <span
                  aria-hidden="true"
                  className={cn(
                    "block h-4 animate-pulse rounded-md bg-secondary motion-reduce:animate-none",
                    SHIMMER_WIDTH[index],
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
