"use client";

import { useState } from "react";

import Alertdialog from "@/components/Alertdialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "@/components/ui/toast";
import type { AccessLevel } from "@/interface/files";
import {
  type DriveSyncSettings,
  type DriveSyncUpdate,
  pickGoogleDriveFiles,
  useDriveSync,
  useRunDriveSync,
  useSaveDriveSync,
  useStopDriveSync,
} from "@/services/google-drive";
import { useDriveConnectResult } from "@/hooks/useDriveConnectResult";
import { useServerStatus } from "@/services/status";
import { getApiErrorMessage } from "@/utils/api-error";

type DriveSyncForm = Omit<DriveSyncUpdate, "timezone">;

const EMPTY_FORM: DriveSyncForm = {
  folder_id: "",
  folder_name: "",
  sync_time: "00:00",
  access_level: "general",
};
const ACCESS_LEVELS = { general: "General", confidential: "Confidential" };
const OFFLINE_MESSAGE = "Google Drive needs internet. PEKA is offline.";

function savedForm(current: DriveSyncSettings | null | undefined): DriveSyncForm {
  if (!current) return EMPTY_FORM;
  const { folder_id, folder_name, sync_time, access_level } = current;
  return { folder_id, folder_name, sync_time: sync_time.slice(0, 5), access_level };
}

export default function DriveSync() {
  const { offline, configured } = useServerStatus();
  const enabled = configured?.google_drive ?? false;
  const sync = useDriveSync(enabled);
  const save = useSaveDriveSync();
  const run = useRunDriveSync();
  const stop = useStopDriveSync();
  // Only the admin's unsaved edits; the rest comes from the server, so a refetch never wipes them.
  const [draft, setDraft] = useState<Partial<DriveSyncForm>>({});
  const [isPicking, setIsPicking] = useState(false);
  const [confirmStop, setConfirmStop] = useState(false);
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const current = sync.data;
  const form = { ...savedForm(current), ...draft };

  // The picker closes with the consent redirect, so the admin picks again.
  useDriveConnectResult("Google Drive connected. Choose the folder to sync.");

  if (!enabled) return null;

  async function chooseFolder() {
    if (offline) return toast.add({ title: OFFLINE_MESSAGE, type: "warning" });
    setIsPicking(true);
    try {
      const [folder] = await pickGoogleDriveFiles(() => true, true);
      if (folder)
        setDraft((value) => ({ ...value, folder_id: folder.id, folder_name: folder.name }));
    } catch (error) {
      toast.add({
        title: getApiErrorMessage(error, "Google Drive is unavailable."),
        type: "error",
      });
    } finally {
      setIsPicking(false);
    }
  }

  function runNow() {
    if (offline) return toast.add({ title: OFFLINE_MESSAGE, type: "warning" });
    run.mutate(undefined, {
      onSuccess: () => toast.add({ title: "Sync starts within a minute.", type: "success" }),
      onError: (error) =>
        toast.add({ title: getApiErrorMessage(error, "Unable to start the sync."), type: "error" }),
    });
  }

  function stopSync() {
    stop.mutate(undefined, {
      onSuccess: () => {
        setDraft({});
        setConfirmStop(false);
        toast.add({ title: "Folder sync stopped.", type: "success" });
      },
      onError: () => toast.add({ title: "Unable to stop the folder sync.", type: "error" }),
    });
  }

  return (
    <>
      <form
        className="flex flex-col gap-4 rounded-xl border border-border p-5"
        onSubmit={(event) => {
          event.preventDefault();
          save.mutate(
            { ...form, timezone },
            {
              onSuccess: () => {
                setDraft({});
                toast.add({ title: "Folder sync saved.", type: "success" });
              },
              onError: (error) =>
                toast.add({
                  title: getApiErrorMessage(error, "Unable to save the folder sync."),
                  type: "error",
                }),
            },
          );
        }}
      >
        <div>
          <h2 className="font-semibold">Google Drive folder sync</h2>
          <p className="mt-1 text-sm text-muted">
            Once a day, new and edited files in this folder and its subfolders are added to the
            knowledge base, and files deleted from it are removed. Files already in the folder when
            you pick it are skipped until they are edited.
          </p>
        </div>
        {sync.isLoading ? (
          <div
            role="status"
            aria-label="Loading folder sync"
            className="h-24 animate-pulse rounded-lg bg-secondary motion-reduce:animate-none"
          />
        ) : sync.isError ? (
          <p className="text-sm text-danger">Unable to load folder sync.</p>
        ) : (
          <>
            {current && (
              <div
                className="flex flex-col gap-1 rounded-lg bg-muted/40 p-3 text-sm"
                aria-live="polite"
              >
                <p>
                  Reads <span className="font-medium">{current.folder_name}</span> with{" "}
                  {current.owner_email}’s Google Drive.
                </p>
                <p className="text-muted">
                  {current.run_requested
                    ? "Syncing, or starting within a minute…"
                    : current.last_synced_at
                      ? `Last run ${new Date(current.last_synced_at).toLocaleString()}: ${current.last_result}`
                      : "Not run yet."}
                </p>
              </div>
            )}
            <div className="flex flex-col gap-1 text-sm">
              Folder
              <div className="flex items-center gap-3">
                <Button
                  type="button"
                  variant="outline"
                  disabled={isPicking}
                  aria-disabled={offline || undefined}
                  onClick={() => void chooseFolder()}
                >
                  {form.folder_id ? "Change folder" : "Choose folder"}
                </Button>
                <span className="truncate text-muted">
                  {form.folder_name || "No folder chosen"}
                </span>
              </div>
            </div>
            <label className="flex flex-col gap-1 text-sm">
              Daily sync time ({timezone})
              <Input
                required
                type="time"
                value={form.sync_time}
                onChange={(e) => setDraft({ ...draft, sync_time: e.target.value })}
              />
            </label>
            {current && current.timezone !== timezone && (
              <p className="text-sm text-muted">
                Saved for {current.timezone}. Saving switches it to this browser’s time zone.
              </p>
            )}
            <div className="flex flex-col gap-1 text-sm">
              Access level for synced files
              <Select
                items={ACCESS_LEVELS}
                value={form.access_level}
                onValueChange={(value) =>
                  value && setDraft({ ...draft, access_level: value as AccessLevel })
                }
              >
                <SelectTrigger aria-label="Access level for synced files">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(ACCESS_LEVELS).map(([value, label]) => (
                    <SelectItem key={value} value={value}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-wrap gap-3">
              <Button type="submit" disabled={!form.folder_id || save.isPending}>
                {save.isPending ? "Saving…" : "Save folder sync"}
              </Button>
              {current && (
                <>
                  <Button
                    type="button"
                    variant="outline"
                    disabled={run.isPending || current.run_requested}
                    aria-disabled={offline || undefined}
                    onClick={runNow}
                  >
                    Sync now
                  </Button>
                  <Button
                    type="button"
                    variant="destructive"
                    disabled={stop.isPending}
                    onClick={() => setConfirmStop(true)}
                  >
                    Stop syncing
                  </Button>
                </>
              )}
            </div>
          </>
        )}
      </form>
      <Alertdialog
        open={confirmStop}
        onOpenChange={setConfirmStop}
        title="Stop syncing this folder?"
        description="Files already synced stay in the knowledge base."
        confirmLabel="Stop syncing"
        onConfirm={stopSync}
        pending={stop.isPending}
      />
    </>
  );
}
