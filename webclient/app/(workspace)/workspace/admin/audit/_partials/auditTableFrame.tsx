import type { ReactNode } from "react";

import { Table, TableBody, TableHead, TableHeader, TableRow } from "@/components/ui/table";

export const AUDIT_TABLE_COLUMNS = ["Type", "Created", "Actor", "Summary"] as const;

export default function AuditTableFrame({ children }: { children: ReactNode }) {
  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-background shadow-sm">
      <Table>
        <TableHeader className="bg-secondary/70">
          <TableRow className="border-border hover:bg-secondary/70">
            {AUDIT_TABLE_COLUMNS.map((column) => (
              <TableHead key={column}>
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
