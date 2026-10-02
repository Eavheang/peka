export const AUDIT_EVENT_TYPE_LABELS = {
  sync: "Sync",
  query: "Query",
  system: "System",
} as const;

export type AuditEventType = keyof typeof AUDIT_EVENT_TYPE_LABELS;

export interface AuditEvent {
  id: string;
  type: AuditEventType;
  actor_id: string | null;
  summary: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface AuditEventsResponse {
  items: AuditEvent[];
  next_cursor: string | null;
}
