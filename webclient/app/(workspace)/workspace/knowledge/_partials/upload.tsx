"use client";

import { ChangeEvent, DragEvent, useRef, useState } from "react";
import { FileText, FileUp, Loader2, Plus, Trash2, UploadCloud, XCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { useUploadFiles } from "@/services/files";

const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;
const ACCEPTED_EXTENSIONS = [".pdf", ".docx", ".pptx", ".xlsx", ".md", ".txt"];

function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function Upload() {
  const inputRef = useRef<HTMLInputElement>(null);

  const [isDragging, setIsDragging] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);

  const upload = useUploadFiles();

  function ingestFiles(selected: File[]) {
    setUploadError("");

    const valid: File[] = [];
    const errors: string[] = [];

    selected.forEach((file) => {
      const extension = `.${file.name.split(".").pop()?.toLowerCase() ?? ""}`;

      if (!ACCEPTED_EXTENSIONS.includes(extension)) {
        errors.push(`${file.name} is not supported.`);
        return;
      }

      if (file.size > MAX_UPLOAD_BYTES) {
        errors.push(`${file.name} exceeds the 25 MB limit.`);
        return;
      }

      valid.push(file);
    });

    if (errors.length) {
      setUploadError(errors.join(" "));
    }

    if (valid.length) {
      setPendingFiles((current) => {
        const existing = new Set(
          current.map((file) => `${file.name}-${file.size}-${file.lastModified}`),
        );

        return [
          ...current,
          ...valid.filter(
            (file) => !existing.has(`${file.name}-${file.size}-${file.lastModified}`),
          ),
        ];
      });
    }
  }

  function choose(event: ChangeEvent<HTMLInputElement>) {
    ingestFiles(Array.from(event.target.files ?? []));
    event.target.value = "";
  }

  function drop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragging(false);

    ingestFiles(Array.from(event.dataTransfer.files));
  }

  function removeFile(index: number) {
    setPendingFiles((current) => current.filter((_, fileIndex) => fileIndex !== index));
  }

  function proceed() {
    if (!pendingFiles.length) return;

    setUploadError("");

    upload.mutate(pendingFiles, {
      onSuccess: () => {
        setPendingFiles([]);
      },
      onError: (error) => {
        setUploadError(error instanceof Error ? error.message : "Upload failed.");
      },
    });
  }

  const hasFiles = pendingFiles.length > 0;

  return (
    <div className="mx-auto w-full">
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={ACCEPTED_EXTENSIONS.join(",")}
        className="hidden"
        onChange={choose}
      />

      <div className="flex h-72 flex-col overflow-hidden rounded-2xl border border-border bg-background">
        {!hasFiles ? (
          <div
            className={`flex min-h-72 cursor-pointer flex-col items-center justify-center px-6 py-10 text-center transition-colors ${
              isDragging ? "bg-primary/5" : "hover:bg-secondary/30"
            }`}
            onClick={() => inputRef.current?.click()}
            onDragEnter={(event) => {
              event.preventDefault();
              setIsDragging(true);
            }}
            onDragOver={(event) => {
              event.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={(event) => {
              if (event.currentTarget.contains(event.relatedTarget as Node)) {
                return;
              }

              setIsDragging(false);
            }}
            onDrop={drop}
          >
            <div
              className={`grid size-12 place-items-center rounded-2xl transition-colors ${
                isDragging ? "bg-primary text-primary-foreground" : "bg-secondary text-foreground"
              }`}
            >
              <UploadCloud size={22} />
            </div>

            <h2 className="mt-5 text-lg font-semibold">
              {isDragging ? "Drop your files here" : "Upload documents"}
            </h2>

            <p className="mt-2 max-w-sm text-sm leading-6 text-copy">
              Drag and drop documents here, or choose files from your computer.
            </p>

            <Button
              type="button"
              className="mt-5"
              onClick={(event) => {
                event.stopPropagation();
                inputRef.current?.click();
              }}
            >
              <FileUp size={16} />
              Choose files
            </Button>

            <p className="mt-4 text-xs text-muted-foreground">
              PDF, DOCX, PPTX, XLSX, MD or TXT · Max 25 MB per file
            </p>
          </div>
        ) : (
          <>
            {/* Header */}
            <div className="flex items-center justify-between gap-4 border-b border-border px-5 py-2">
              <div>
                <h2 className="font-semibold">Documents</h2>

                <p className="mt-0.5 text-sm text-copy">
                  {pendingFiles.length} {pendingFiles.length === 1 ? "file" : "files"} ready to
                  upload
                </p>
              </div>

              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={upload.isPending}
                onClick={() => inputRef.current?.click()}
              >
                <Plus size={15} />
                Add files
              </Button>
            </div>

            {/* File queue */}
            <div
              className={`min-h-0 flex-1 overflow-hidden px-3 transition-colors ${
                isDragging ? "bg-primary/5" : ""
              }`}
              onDragEnter={(event) => {
                event.preventDefault();
                setIsDragging(true);
              }}
              onDragOver={(event) => {
                event.preventDefault();
                setIsDragging(true);
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={drop}
            >
              {isDragging && (
                <div className="mb-3 rounded-xl border border-dashed border-primary bg-primary/5 px-4 py-2 text-center text-sm font-medium text-primary">
                  Drop files to add them
                </div>
              )}

              <ul className="h-full max-h-none space-y-1 overflow-y-auto">
                {pendingFiles.map((file, index) => (
                  <li
                    key={`${file.name}-${file.lastModified}-${index}`}
                    className="group flex items-center gap-3 rounded-xl px-3 py-2.5 hover:bg-secondary/50"
                  >
                    <div className="grid size-9 shrink-0 place-items-center rounded-lg bg-secondary">
                      <FileText aria-hidden="true" size={17} className="text-copy" />
                    </div>

                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{file.name}</p>

                      <p className="mt-0.5 text-xs text-muted-foreground">
                        {formatFileSize(file.size)}
                      </p>
                    </div>

                    <Button
                      type="button"
                      aria-label={`Remove ${file.name}`}
                      variant="ghost"
                      size="icon"
                      disabled={upload.isPending}
                      className="size-8 text-muted-foreground hover:text-danger"
                      onClick={() => removeFile(index)}
                    >
                      <Trash2 size={15} />
                    </Button>
                  </li>
                ))}
              </ul>
            </div>

            {/* Error */}
            {uploadError && (
              <div className="mx-5 mb-4 flex items-start gap-2 rounded-xl bg-danger/10 px-3 py-2.5 text-sm text-danger">
                <XCircle className="mt-0.5 shrink-0" size={16} />
                <p>{uploadError}</p>
              </div>
            )}

            {/* Upload progress */}
            {upload.isPending && (
              <div className="px-5 pb-4">
                <div className="mb-2 flex items-center justify-between text-xs text-copy">
                  <span>Uploading documents…</span>
                  <span>Please keep this page open</span>
                </div>

                <Progress value={null} />
              </div>
            )}

            {/* Footer */}
            <div className="flex items-center justify-between gap-4 border-t border-border bg-secondary/20 px-5 py-2 ">
              <button
                type="button"
                disabled={upload.isPending}
                onClick={() => setPendingFiles([])}
                className="rounded-lg px-3 py-2 text-sm font-medium text-copy transition-colors hover:bg-secondary hover:text-foreground disabled:pointer-events-none disabled:opacity-50"
              >
                Clear all
              </button>

              <Button
                type="button"
                disabled={upload.isPending}
                className="h-11 px-5"
                onClick={proceed}
              >
                {upload.isPending ? (
                  <Loader2 className="animate-spin" size={16} />
                ) : (
                  <FileUp size={16} />
                )}

                {upload.isPending
                  ? "Uploading…"
                  : `Upload ${pendingFiles.length} ${pendingFiles.length === 1 ? "file" : "files"}`}
              </Button>
            </div>
          </>
        )}
      </div>

      {!hasFiles && uploadError && (
        <div className="mt-3 flex items-start gap-2 text-sm text-danger">
          <XCircle className="mt-0.5 shrink-0" size={16} />
          <p>{uploadError}</p>
        </div>
      )}
    </div>
  );
}
