"use client";

import { useEffect, useState } from "react";
import { Download, FileText, RotateCcw, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { StoredFile } from '@/interface/files';

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

const PAGE_SIZE = 5;

type KnowledgeTableProps = {
  sources: StoredFile[];
  onRetry: (id: string) => void;
  onDownload: (file: StoredFile) => void;
  onRemove: (id: string) => void;
};

export function KnowledgeTable({ sources, onRetry, onDownload, onRemove }: KnowledgeTableProps) {
  const [page, setPage] = useState(1);
  const pageCount = Math.max(1, Math.ceil(sources.length / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const pageSources = sources.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  useEffect(() => {
    if (page > pageCount) setPage(pageCount);
  }, [page, pageCount]);

  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-background shadow-sm">
      <Table>
        <TableHeader className="bg-secondary/70">
          <TableRow className="border-border hover:bg-secondary/70">
            <TableHead className="px-5 py-4 text-xs uppercase tracking-[0.14em] text-muted">
              Name
            </TableHead>
            <TableHead className="px-5 py-4 text-xs uppercase tracking-[0.14em] text-muted">
              Uploaded
            </TableHead>
            <TableHead className="px-5 py-4 text-xs uppercase tracking-[0.14em] text-muted">
              Type
            </TableHead>
            <TableHead className="px-5 py-4 text-xs uppercase tracking-[0.14em] text-muted">
              Access
            </TableHead>
            <TableHead className="px-5 py-4 text-xs uppercase tracking-[0.14em] text-muted">
              Status
            </TableHead>
            <TableHead className="px-5 py-4 text-right text-xs uppercase tracking-[0.14em] text-muted">
              Actions
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {pageSources.map((file) => (
            <TableRow key={file.id} className="border-border hover:bg-secondary/40">
              <TableCell className="max-w-64 px-5 py-4">
                <div className="flex min-w-0 items-center gap-3">
                  <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-secondary text-muted-foreground">
                    <FileText aria-hidden="true" size={17} />
                  </span>
                  <span className="truncate font-medium">{fileName(file)}</span>
                </div>
              </TableCell>
              <TableCell className="px-5 py-4">
                {new Date(file.created_at).toLocaleDateString()}
              </TableCell>
              <TableCell className="px-5 py-4">
                {file.content_type?.split("/").pop()?.toUpperCase() ?? "File"}
              </TableCell>
              <TableCell className="px-5 py-4">
                <Badge variant="outline">{file.access_level}</Badge>
              </TableCell>
              <TableCell className="px-5 py-4">
                <Badge className={statusClass(file.okf_status)}>
                  {statusLabel(file.okf_status)}
                </Badge>
                {file.okf_status === "failed" && file.okf_error && (
                  <p className="mt-1 max-w-48 text-xs text-danger">{file.okf_error}</p>
                )}
              </TableCell>
              <TableCell className="px-5 py-4">
                <div className="flex justify-end gap-1">
                  {file.okf_status === "failed" && (
                    <Button
                      aria-label={`Retry ${fileName(file)}`}
                      size="icon"
                      variant="ghost"
                      onClick={() => onRetry(file.id)}
                    >
                      <RotateCcw size={16} />
                    </Button>
                  )}
                  <Button
                    aria-label={`Download ${fileName(file)}`}
                    size="icon"
                    variant="ghost"
                    onClick={() => onDownload(file)}
                  >
                    <Download size={16} />
                  </Button>
                  {(file.okf_status === "queued" || file.okf_status === "failed") && (
                    <Button
                      aria-label={`Remove ${fileName(file)}`}
                      size="icon"
                      variant="ghost"
                      onClick={() => onRemove(file.id)}
                    >
                      <Trash2 size={16} />
                    </Button>
                  )}
                </div>
              </TableCell>
            </TableRow>
          ))}
          {!sources.length && (
            <TableRow className="border-border hover:bg-secondary/40">
              <TableCell className="px-5 py-16 text-center" colSpan={6}>
                <div className="mx-auto max-w-xs">
                  <FileText className="mx-auto text-muted-foreground" size={24} />
                  <p className="mt-3 font-medium">No sources yet</p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Upload your first document to start building workspace knowledge.
                  </p>
                </div>
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
      {pageCount > 1 && (
        <div className="flex items-center justify-between border-t border-border px-5 py-3">
          <p className="text-sm text-muted-foreground">
            Page {currentPage} of {pageCount}
          </p>
          <div className="flex gap-2">
            <Button
              disabled={currentPage === 1}
              variant="outline"
              onClick={() => setPage((value) => value - 1)}
            >
              Previous
            </Button>
            <Button
              disabled={currentPage === pageCount}
              variant="outline"
              onClick={() => setPage((value) => value + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
