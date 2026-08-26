export type FileIndexStatus = 'queued' | 'processing' | 'completed' | 'failed';

export interface StoredFile {
  id: string;
  path: string;
  content_type: string | null;
  sha256: string | null;
  author_id: string;
  access_level: 'general' | 'confidential';
  created_at: string;
  okf_status: FileIndexStatus;
  okf_attempts: number;
  okf_error: string | null;
}
