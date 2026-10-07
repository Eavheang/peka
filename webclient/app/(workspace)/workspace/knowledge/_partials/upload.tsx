"use client";

import { ChangeEvent, DragEvent, MouseEvent, useEffect, useRef, useState } from "react";
import {
  FileText,
  FileUp,
  HardDrive,
  Laptop,
  Loader2,
  Plus,
  Trash2,
  UploadCloud,
  XCircle,
} from "lucide-react";

import { Button, buttonVariants } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { AccessLevel } from "@/interface/files";
import { useUploadFiles } from "@/services/files";
import { pickGoogleDriveFiles, useImportDriveFiles } from "@/services/google-drive";
import { useGetCurrentUser } from "@/services/auth";
import { getApiErrorMessage } from "@/utils/api-error";
import { getStoredToken } from "@/utils/auth-storage";
import { toast } from "@/components/ui/toast";

const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;
const ACCEPTED_EXTENSIONS = [".pdf", ".docx", ".pptx", ".xlsx", ".md", ".txt"];
// Drive picks queued before the Google consent redirect, restored when the user comes back.
const DRIVE_PICKS_STORAGE_KEY = "peka_pending_drive_picks";

function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

// Local files carry `file`; Google Drive picks carry `driveId` and are downloaded by the backend.
type PendingFile = {
  key: string;
  name: string;
  size: number | null;
  accessLevel: AccessLevel;
  file?: File;
  driveId?: string;
};

function fileKey(file: File) {
  return `${file.name}-${file.size}-${file.lastModified}`;
}

// sessionStorage is untrusted: only general|confidential count, and non-admins cannot restore confidential.
function clampRestoredAccessLevel(value: unknown, canSetConfidential: boolean): AccessLevel {
  const accessLevel = value === "general" || value === "confidential" ? value : "general";
  return accessLevel === "confidential" && !canSetConfidential ? "general" : accessLevel;
}

export function Upload() {
  const inputRef = useRef<HTMLInputElement>(null);

  const [isDragging, setIsDragging] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [pendingFiles, setPendingFiles] = useState<PendingFile[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set());
  const [bulkAccessLevel, setBulkAccessLevel] = useState("");

  const [isPickingDrive, setIsPickingDrive] = useState(false);
  // Hold Drive picks from the OAuth redirect until the current user's role is known.
  const [restoredDrivePicks, setRestoredDrivePicks] = useState<PendingFile[] | null>(null);

  const upload = useUploadFiles();
  const driveImport = useImportDriveFiles();
  const isUploading = upload.isPending || driveImport.isPending;
  const user = useGetCurrentUser(getStoredToken("peka_access_token") ?? "");
  const canSetConfidential = user.data?.role === "admin";

  useEffect(() => {
    const url = new URL(window.location.href);
    const result = url.searchParams.get("google_drive");
    if (result) {
      toast.add(
        result === "connected"
          ? { title: "Google Drive connected.", type: "success" }
          : { title: "Google Drive could not be connected. Please try again.", type: "error" },
      );
      url.searchParams.delete("google_drive");
      window.history.replaceState(null, "", url);
    }

    try {
      const saved = window.sessionStorage.getItem(DRIVE_PICKS_STORAGE_KEY);
      window.sessionStorage.removeItem(DRIVE_PICKS_STORAGE_KEY);
      if (saved) setRestoredDrivePicks(JSON.parse(saved) as PendingFile[]);
    } catch {
      // Storage blocked or corrupt: the user picks the files again.
    }
  }, []);

  useEffect(() => {
    if (!restoredDrivePicks) return;
    // Do not clamp until role is known; on a failed /me, treat as non-admin.
    if (!user.isSuccess && !user.isError) return;

    const allowConfidential = user.isSuccess && user.data.role === "admin";
    addPending(
      restoredDrivePicks.map((item) => ({
        ...item,
        accessLevel: clampRestoredAccessLevel(item.accessLevel, allowConfidential),
      })),
    );
    setRestoredDrivePicks(null);
  }, [restoredDrivePicks, user.isSuccess, user.isError, user.data?.role]);

  // Runs before the Google consent redirect, which reloads the page.
  function beforeDriveConnect() {
    const localCount = pendingFiles.filter(({ file }) => file).length;
    if (
      localCount &&
      !window.confirm(
        `Connecting Google Drive reloads this page and clears ${localCount} local ${localCount === 1 ? "file" : "files"} from the upload queue. Continue?`,
      )
    ) {
      return false;
    }
    try {
      window.sessionStorage.setItem(
        DRIVE_PICKS_STORAGE_KEY,
        JSON.stringify(pendingFiles.filter(({ driveId }) => driveId)),
      );
    } catch {
      // Storage blocked: Drive picks are lost with the reload.
    }
    return true;
  }

  function ingestFiles(selected: File[]) {
    setUploadError("");

    const valid: PendingFile[] = [];
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

      valid.push({
        key: fileKey(file),
        name: file.name,
        size: file.size,
        accessLevel: "general",
        file,
      });
    });

    if (errors.length) {
      setUploadError(errors.join(" "));
    }

    addPending(valid);
  }

  function addPending(items: PendingFile[]) {
    if (!items.length) return;

    setPendingFiles((current) => {
      const existing = new Set(current.map(({ key }) => key));

      return [...current, ...items.filter(({ key }) => !existing.has(key))];
    });
  }

  async function chooseFromDrive() {
    setUploadError("");
    setIsPickingDrive(true);

    try {
      const docs = await pickGoogleDriveFiles(beforeDriveConnect);
      addPending(
        docs.map(({ id, name, sizeBytes }) => ({
          key: `drive-${id}`,
          name,
          size: sizeBytes ?? null,
          accessLevel: "general",
          driveId: id,
        })),
      );
    } catch (error) {
      setUploadError(getApiErrorMessage(error, "Google Drive is unavailable."));
    } finally {
      setIsPickingDrive(false);
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
    const fileToRemove = pendingFiles[index];
    if (!fileToRemove) return;

    setPendingFiles((current) => current.filter((_, fileIndex) => fileIndex !== index));
    setSelectedFiles((current) => {
      const next = new Set(current);
      next.delete(fileToRemove.key);
      return next;
    });
  }

  function toggleFile(key: string) {
    setSelectedFiles((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function applyBulkAccess(level: AccessLevel) {
    setPendingFiles((current) =>
      current.map((pendingFile) =>
        selectedFiles.has(pendingFile.key) ? { ...pendingFile, accessLevel: level } : pendingFile,
      ),
    );
    setBulkAccessLevel("");
  }

  async function proceed() {
    if (!pendingFiles.length) return;

    setUploadError("");

    const local = pendingFiles.flatMap(({ file, accessLevel }) =>
      file ? [{ file, accessLevel }] : [],
    );
    const drive = pendingFiles.flatMap(({ driveId, accessLevel }) =>
      driveId ? [{ id: driveId, accessLevel }] : [],
    );

    // Drop each batch from the queue once stored so a retry never re-sends it.
    try {
      if (local.length) {
        await upload.mutateAsync(local);
        setPendingFiles((current) => current.filter(({ file }) => !file));
      }
      if (drive.length) {
        await driveImport.mutateAsync(drive);
        setPendingFiles((current) => current.filter(({ driveId }) => !driveId));
      }
      setSelectedFiles(new Set());
      setBulkAccessLevel("");
    } catch (error) {
      setUploadError(getApiErrorMessage(error, "Upload failed."));
    }
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
            <div className="flex items-center gap-2">
              <UploadCloud
                aria-hidden="true"
                size={20}
                className={isDragging ? "text-primary" : "text-copy"}
              />
              <h2 className="text-lg font-semibold">
                {isDragging ? "Drop your files here" : "Upload documents"}
              </h2>
            </div>

            <p className="mt-1.5 text-sm text-copy">
              Drag and drop anywhere in this box, or pick a source.
            </p>

            <div className="mt-6 grid w-full max-w-lg gap-3 sm:grid-cols-2">
              {/* The computer card has no handler: its click bubbles to the box, which opens the file dialog. */}
              {[
                {
                  title: "Your computer",
                  hint: "Browse local files",
                  icon: <Laptop size={18} />,
                  iconClass: "bg-primary text-primary-foreground",
                },
                {
                  title: "Google Drive",
                  hint: isPickingDrive ? "Opening picker…" : "Import from Drive",
                  icon: isPickingDrive ? (
                    <Loader2 className="animate-spin" size={18} />
                  ) : (
                    <HardDrive size={18} />
                  ),
                  iconClass: "bg-secondary text-foreground",
                  disabled: isPickingDrive,
                  onClick: (event: MouseEvent) => {
                    event.stopPropagation();
                    void chooseFromDrive();
                  },
                },
              ].map(({ title, hint, icon, iconClass, disabled, onClick }) => (
                <button
                  key={title}
                  type="button"
                  disabled={disabled}
                  className="flex items-center gap-3 rounded-xl border border-border bg-background p-3 text-left transition-colors hover:border-primary/50 hover:bg-secondary/40 disabled:pointer-events-none disabled:opacity-50"
                  onClick={onClick}
                >
                  <span
                    className={`grid size-10 shrink-0 place-items-center rounded-lg ${iconClass}`}
                  >
                    {icon}
                  </span>
                  <span>
                    <span className="block text-sm font-medium">{title}</span>
                    <span className="block text-xs text-muted-foreground">{hint}</span>
                  </span>
                </button>
              ))}
            </div>

            <p className="mt-5 text-xs text-muted-foreground">
              PDF, DOCX, PPTX, XLSX, MD or TXT · Max 25 MB per file
            </p>
          </div>
        ) : (
          <>
            {/* Header */}
            <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border px-5 py-2">
              <div>
                <h2 className="font-semibold">Documents</h2>

                <p className="mt-0.5 text-sm text-copy">
                  {pendingFiles.length} {pendingFiles.length === 1 ? "file" : "files"} ready to
                  upload
                </p>
              </div>

              <div className="flex items-center gap-2">
                {selectedFiles.size > 0 && (
                  <Select
                    value={bulkAccessLevel || null}
                    onValueChange={(value) => {
                      if (!value) return;
                      const accessLevel = value as AccessLevel;
                      setBulkAccessLevel(accessLevel);
                      if (
                        accessLevel === "general" ||
                        (accessLevel === "confidential" && canSetConfidential)
                      ) {
                        applyBulkAccess(accessLevel);
                      }
                    }}
                  >
                    <SelectTrigger
                      disabled={isUploading}
                      aria-label={`Set access for ${selectedFiles.size} selected ${selectedFiles.size === 1 ? "file" : "files"}`}
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
                      {canSetConfidential && (
                        <SelectItem value="confidential">Confidential</SelectItem>
                      )}
                    </SelectContent>
                  </Select>
                )}

                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={isUploading}
                  onClick={() => inputRef.current?.click()}
                >
                  <Plus size={15} />
                  Add files
                </Button>

                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={isUploading || isPickingDrive}
                  onClick={() => void chooseFromDrive()}
                >
                  {isPickingDrive ? (
                    <Loader2 className="animate-spin" size={15} />
                  ) : (
                    <HardDrive size={15} />
                  )}
                  Google Drive
                </Button>
              </div>
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
                {pendingFiles.map(({ key, name, size, driveId, accessLevel }, index) => (
                  <li
                    key={key}
                    className="group flex items-center gap-3 rounded-xl px-3 py-2.5 hover:bg-secondary/50"
                  >
                    <input
                      type="checkbox"
                      checked={selectedFiles.has(key)}
                      aria-label={`Select ${name}`}
                      className="size-4 shrink-0 accent-primary"
                      disabled={isUploading}
                      onChange={() => toggleFile(key)}
                    />

                    <div className="grid size-9 shrink-0 place-items-center rounded-lg bg-secondary">
                      <FileText aria-hidden="true" size={17} className="text-copy" />
                    </div>

                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{name}</p>

                      <div className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
                        {driveId && <span>Google Drive</span>}
                        {driveId && size !== null && <span aria-hidden="true">·</span>}
                        {size !== null && <span>{formatFileSize(size)}</span>}
                        <span aria-hidden="true">·</span>
                        <span className="capitalize">{accessLevel}</span>
                      </div>
                    </div>

                    <Button
                      type="button"
                      aria-label={`Remove ${name}`}
                      variant="ghost"
                      size="icon"
                      disabled={isUploading}
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
            {isUploading && (
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
                disabled={isUploading}
                onClick={() => {
                  setPendingFiles([]);
                  setSelectedFiles(new Set());
                  setBulkAccessLevel("");
                }}
                className="rounded-lg px-3 py-2 text-sm font-medium text-copy transition-colors hover:bg-secondary hover:text-foreground disabled:pointer-events-none disabled:opacity-50"
              >
                Clear all
              </button>

              <Button type="button" disabled={isUploading} className="h-11 px-5" onClick={proceed}>
                {isUploading ? (
                  <Loader2 className="animate-spin" size={16} />
                ) : (
                  <FileUp size={16} />
                )}

                {isUploading
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
