export type AuditEventType = "sync" | "query" | "system";

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
