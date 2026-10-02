"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { AUDIT_EVENT_TYPE_LABELS, type AuditEventType } from "@/interface/audit";

export type AuditTypeFilterValue = "all" | AuditEventType;

const FILTERS: { value: AuditTypeFilterValue; label: string }[] = [
  { value: "all", label: "All" },
  ...(Object.entries(AUDIT_EVENT_TYPE_LABELS) as [AuditEventType, string][]).map(
    ([value, label]) => ({ value, label }),
  ),
];

function isAuditTypeFilter(value: unknown): value is AuditTypeFilterValue {
  return FILTERS.some((filter) => filter.value === value);
}

export default function AuditTypeFilter({
  value,
  onChange,
}: {
  value: AuditTypeFilterValue;
  onChange: (value: AuditTypeFilterValue) => void;
}) {
  return (
    <div className="flex items-center gap-3">
      <span id="audit-type-label" className="text-sm text-muted">
        Type
      </span>
      <Select
        value={value}
        onValueChange={(next) => {
          if (isAuditTypeFilter(next)) onChange(next);
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
  );
}
