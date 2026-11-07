export type FileIndexStatus = "queued" | "processing" | "completed" | "failed";
export type AccessLevel = "general" | "confidential";

export interface StoredFile {
  id: string;
  path: string;
  content_type: string | null;
  sha256: string | null;
  author_id: string;
  access_level: AccessLevel;
  created_at: string;
  index_status: FileIndexStatus;
  index_attempts: number;
  index_error: string | null;
}
