"use client";

import { useEffect, useState } from "react";
import { Download, FileText, RotateCcw, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { AccessLevel, StoredFile } from "@/interface/files";
import { useUpdateFileAccessLevel } from "@/services/files";
import { getApiErrorMessage } from "@/utils/api-error";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
function fileName(file: StoredFile) {
  return file.path.split("/").pop() ?? file.path;
}

function fileType(file: StoredFile) {
  const ext = fileName(file).split(".").pop();
  return ext && ext !== fileName(file) ? ext.toUpperCase() : "File";
}

function statusLabel(status: StoredFile["index_status"]) {
  return { queued: "Queued", processing: "Indexing", completed: "Indexed", failed: "Failed" }[
    status
  ];
}

function statusClass(status: StoredFile["index_status"]) {
  return status === "completed"
    ? "border-success bg-success text-success-foreground"
    : status === "failed"
      ? "border-danger bg-danger text-danger-foreground"
      : "border-border bg-secondary text-secondary-foreground";
}

const PAGE_SIZE = 5;

type KnowledgeTableProps = {
  sources: StoredFile[];
  canManageAccess: boolean;
  onRetry: (id: string) => void;
  onDownload: (file: StoredFile) => void;
  onRemove: (id: string) => void;
};

export function KnowledgeTable({
  sources,
  canManageAccess,
  onRetry,
  onDownload,
  onRemove,
}: KnowledgeTableProps) {
  const [page, setPage] = useState(1);
  const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set());
  const [bulkAccessLevel, setBulkAccessLevel] = useState("");
  const [accessError, setAccessError] = useState("");
  const updateAccess = useUpdateFileAccessLevel();
  const pageCount = Math.max(1, Math.ceil(sources.length / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const pageSources = sources.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  useEffect(() => {
    if (page > pageCount) setPage(pageCount);
  }, [page, pageCount]);

  useEffect(() => {
    const sourceIds = new Set(sources.map((source) => source.id));
    setSelectedFiles((current) => {
      const next = new Set(Array.from(current).filter((id) => sourceIds.has(id)));
      return next.size === current.size ? current : next;
    });
  }, [sources]);

  async function applyBulkAccess(accessLevel: AccessLevel) {
    setAccessError("");
    try {
      await Promise.all(
        Array.from(selectedFiles).map((id) => updateAccess.mutateAsync({ id, accessLevel })),
      );
      setSelectedFiles(new Set());
      setBulkAccessLevel("");
    } catch (error) {
      setAccessError(getApiErrorMessage(error, "Unable to update access level."));
    }
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-background shadow-sm">
      {canManageAccess && selectedFiles.size > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-secondary/20 px-5 py-2.5">
          <span className="text-sm font-medium text-copy">{selectedFiles.size} selected</span>
          <Select
            value={bulkAccessLevel || null}
            onValueChange={(value) => {
              if (!value) return;
              const accessLevel = value as AccessLevel;
              setBulkAccessLevel(accessLevel);
              void applyBulkAccess(accessLevel);
            }}
          >
            <SelectTrigger
              disabled={updateAccess.isPending}
              aria-label="Set access for selected files"
              className={buttonVariants({
                variant: "outline",
                size: "sm",
                className: "w-auto min-w-36",
              })}
            >
              <SelectValue placeholder="Set access…" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="general">General</SelectItem>
              <SelectItem value="confidential">Confidential</SelectItem>
            </SelectContent>
          </Select>
          {accessError && <p className="basis-full text-sm text-danger">{accessError}</p>}
        </div>
      )}
      <Table>
        <TableHeader className="bg-secondary/70">
          <TableRow className="border-border hover:bg-secondary/70">
            {canManageAccess && <TableHead className="w-12 px-3 py-4" />}
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
              {canManageAccess && (
                <TableCell className="w-12 px-3 py-4">
                  <input
                    type="checkbox"
                    checked={selectedFiles.has(file.id)}
                    aria-label={`Select ${fileName(file)}`}
                    className="size-4 accent-primary"
                    disabled={updateAccess.isPending}
                    onChange={() => {
                      setSelectedFiles((current) => {
                        const next = new Set(current);
                        if (next.has(file.id)) next.delete(file.id);
                        else next.add(file.id);
                        return next;
                      });
                    }}
                  />
                </TableCell>
              )}
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
              <TableCell className="px-5 py-4">{fileType(file)}</TableCell>
              <TableCell className="px-5 py-4">
                <Badge variant="outline">{file.access_level}</Badge>
              </TableCell>
              <TableCell className="px-5 py-4">
                <Badge className={statusClass(file.index_status)}>
                  {statusLabel(file.index_status)}
                </Badge>
                {file.index_status === "failed" && file.index_error && (
                  <p className="mt-1 max-w-48 text-xs text-danger">{file.index_error}</p>
                )}
              </TableCell>
              <TableCell className="px-5 py-4">
                <div className="flex justify-end gap-1">
                  {file.index_status === "failed" && (
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
                  {(file.index_status === "queued" || file.index_status === "failed") && (
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
              <TableCell className="px-5 py-16 text-center" colSpan={canManageAccess ? 7 : 6}>
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
