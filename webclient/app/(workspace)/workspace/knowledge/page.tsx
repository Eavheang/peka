'use client';

import { ChangeEvent, DragEvent, useMemo, useRef, useState } from 'react';
import { Download, FileUp, Loader2, RotateCcw, Trash2 } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import type { StoredFile } from '@/interface/files';
import { useDeleteFile, useListFiles, useRetryFile, useUploadFiles, downloadFile } from '@/services/files';

const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;
const ACCEPTED_EXTENSIONS = ['.pdf', '.docx', '.pptx', '.xlsx', '.md', '.txt'];

function fileName(file: StoredFile) {
  return file.path.split('/').pop() ?? file.path;
}

function statusLabel(status: StoredFile['okf_status']) {
  return { queued: 'Queued', processing: 'Indexing', completed: 'Indexed', failed: 'Failed' }[status];
}

function statusClass(status: StoredFile['okf_status']) {
  return status === 'completed'
    ? 'border-success bg-success text-success-foreground'
    : status === 'failed'
      ? 'border-danger bg-danger text-danger-foreground'
      : 'border-border bg-secondary text-secondary-foreground';
}

export default function KnowledgePage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const files = useListFiles();
  const upload = useUploadFiles();
  const retry = useRetryFile();
  const remove = useDeleteFile();
  const sources = files.data ?? [];
  const counts = useMemo(
    () => ({
      indexed: sources.filter((file) => file.okf_status === 'completed').length,
      active: sources.filter((file) => file.okf_status === 'queued' || file.okf_status === 'processing').length,
      failed: sources.filter((file) => file.okf_status === 'failed').length,
    }),
    [sources],
  );
  const lastIndexed = sources
    .filter((file) => file.okf_status === 'completed')
    .sort((a, b) => b.created_at.localeCompare(a.created_at))[0]?.created_at;
  const aggregateProgress = sources.length ? Math.round((counts.indexed / sources.length) * 100) : 0;

  function ingestFiles(selected: File[]) {
    setUploadError('');
    const valid: File[] = [];
    const errors: string[] = [];
    selected.forEach((file) => {
      const extension = `.${file.name.split('.').pop()?.toLowerCase() ?? ''}`;
      if (!ACCEPTED_EXTENSIONS.includes(extension)) errors.push(`${file.name}: unsupported type`);
      else if (file.size > MAX_UPLOAD_BYTES) errors.push(`${file.name}: exceeds 25 MB limit`);
      else valid.push(file);
    });
    if (errors.length) setUploadError(errors.join(' · '));
    if (valid.length) upload.mutate(valid, { onError: (error) => setUploadError(error instanceof Error ? error.message : 'Upload failed') });
  }

  function choose(event: ChangeEvent<HTMLInputElement>) {
    ingestFiles(Array.from(event.target.files ?? []));
    event.target.value = '';
  }

  function drop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragging(false);
    ingestFiles(Array.from(event.dataTransfer.files));
  }

  return (
    <section className="mx-auto max-w-6xl space-y-8 p-6 lg:p-10">
      <header className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="mb-2 text-sm font-semibold uppercase tracking-[0.18em] text-primary">Knowledge</p>
          <h1>Knowledge library</h1>
          <p className="mt-3 max-w-2xl">Upload sources for workspace chat. Chat keeps using last healthy index while new sources process.</p>
        </div>
        <div className="rounded-lg border border-border bg-panel px-4 py-3 text-panel-foreground">
          <p className="text-xs uppercase tracking-wider text-panel-foreground/60">Active index</p>
          <p className="mt-1 text-sm font-semibold">{counts.indexed} indexed sources</p>
          {lastIndexed && <p className="text-xs text-panel-foreground/60">Updated {new Date(lastIndexed).toLocaleString()}</p>}
        </div>
      </header>

      <div className="grid gap-3 sm:grid-cols-3">
        {[
          ['Sources', sources.length],
          ['Indexing', counts.active],
          ['Failed', counts.failed],
        ].map(([label, value]) => (
          <div className="rounded-xl border border-border bg-white/40 p-4" key={label}>
            <p className="text-sm text-muted-foreground">{label}</p>
            <p className="mt-1 text-2xl font-semibold">{value}</p>
          </div>
        ))}
      </div>

      <div
        className={`rounded-xl border-2 border-dashed p-8 text-center transition-colors ${isDragging ? 'border-primary bg-primary/5' : 'border-border bg-white/30'}`}
        onDragEnter={(event) => { event.preventDefault(); setIsDragging(true); }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={() => setIsDragging(false)}
        onDrop={drop}
      >
        <FileUp className="mx-auto mb-3 text-primary" size={28} />
        <h2 className="text-xl">Add documents</h2>
        <p className="mx-auto mt-2 max-w-lg text-sm">Drag and drop PDF, DOCX, PPTX, XLSX, Markdown, or text files. Maximum 25 MB per file.</p>
        <input accept={ACCEPTED_EXTENSIONS.join(',')} className="hidden" multiple ref={inputRef} type="file" onChange={choose} />
        <Button className="mt-5" disabled={upload.isPending} onClick={() => inputRef.current?.click()}>
          {upload.isPending ? <Loader2 className="animate-spin" size={16} /> : <FileUp size={16} />}
          Choose files
        </Button>
        {uploadError && <p className="mt-4 text-sm text-danger">{uploadError}</p>}
        {upload.isPending && <Progress className="mx-auto mt-5 max-w-md" value={null} />}
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between gap-4">
          <div><h2 className="text-2xl">Sources</h2><p className="text-sm">{counts.indexed} of {sources.length} sources indexed</p></div>
          <div className="w-32"><Progress value={aggregateProgress} /></div>
        </div>
        <div className="overflow-hidden rounded-xl border border-border bg-white/40">
          <Table>
            <TableHeader><TableRow><TableHead>Name</TableHead><TableHead>Uploaded</TableHead><TableHead>Type</TableHead><TableHead>Access</TableHead><TableHead>Status</TableHead><TableHead className="text-right">Actions</TableHead></TableRow></TableHeader>
            <TableBody>
              {sources.map((file) => (
                <TableRow key={file.id}>
                  <TableCell className="max-w-64 truncate font-medium">{fileName(file)}</TableCell>
                  <TableCell>{new Date(file.created_at).toLocaleDateString()}</TableCell>
                  <TableCell>{file.content_type?.split('/').pop()?.toUpperCase() ?? 'File'}</TableCell>
                  <TableCell><Badge variant="outline">{file.access_level}</Badge></TableCell>
                  <TableCell><Badge className={statusClass(file.okf_status)}>{statusLabel(file.okf_status)}</Badge>{file.okf_error && <p className="mt-1 max-w-48 text-xs text-danger">{file.okf_error}</p>}</TableCell>
                  <TableCell><div className="flex justify-end gap-1">
                    {file.okf_status === 'failed' && <Button aria-label={`Retry ${fileName(file)}`} size="icon" variant="ghost" onClick={() => retry.mutate(file.id)}><RotateCcw size={16} /></Button>}
                    <Button aria-label={`Download ${fileName(file)}`} size="icon" variant="ghost" onClick={() => downloadFile(file)}><Download size={16} /></Button>
                    {(file.okf_status === 'queued' || file.okf_status === 'failed') && <Button aria-label={`Remove ${fileName(file)}`} size="icon" variant="ghost" onClick={() => remove.mutate(file.id)}><Trash2 size={16} /></Button>}
                  </div></TableCell>
                </TableRow>
              ))}
              {!sources.length && <TableRow><TableCell className="py-12 text-center text-muted-foreground" colSpan={6}>No sources yet.</TableCell></TableRow>}
            </TableBody>
          </Table>
        </div>
      </div>
    </section>
  );
}
