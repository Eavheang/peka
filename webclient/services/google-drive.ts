"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { isAxiosError } from "axios";

import type { AccessLevel, StoredFile } from "@/interface/files";
import axiosInstance from "@/utils/axios";

export type DriveDoc = { id: string; name: string; sizeBytes?: number };

type PickerConfig = { access_token: string; api_key: string; app_id: string };

// The backend owns OAuth and downloads; the browser only renders Google's Picker iframe.
// Minimal typing for Google's script globals; no @types package needed.
declare global {
  interface Window {
    gapi?: { load: (name: string, callback: () => void) => void };
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    google?: { picker: any };
  }
}

// Files the backend can store: Office/PDF/text, plus native Google files it exports to Office formats.
const PICKER_MIME_TYPES = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "text/plain",
  "text/markdown",
  "text/x-markdown",
  "application/vnd.google-apps.document",
  "application/vnd.google-apps.spreadsheet",
  "application/vnd.google-apps.presentation",
].join(",");

let pickerScript: Promise<void> | null = null;

function loadPicker() {
  pickerScript ??= new Promise<void>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://apis.google.com/js/api.js";
    script.onload = () => window.gapi?.load("picker", resolve);
    script.onerror = () => {
      pickerScript = null;
      reject(new Error("Unable to load Google Drive."));
    };
    document.head.appendChild(script);
  });
  return pickerScript;
}

/**
 * Opens the Drive picker; redirects to Google consent first when the account is not connected.
 * `beforeConnect` runs before that redirect and can cancel it by returning false.
 * `folder`: pick one folder for admin folder sync, which needs read access to the whole Drive.
 */
export async function pickGoogleDriveFiles(
  beforeConnect: () => boolean,
  folder = false,
): Promise<DriveDoc[]> {
  const base = folder ? "/integrations/google/sync" : "/integrations/google";
  let config: PickerConfig;
  try {
    config = (await axiosInstance.get<PickerConfig>(`${base}/picker`)).data;
  } catch (error) {
    if (isAxiosError(error) && error.response?.status === 409) {
      if (!beforeConnect()) return [];
      const { url } = (await axiosInstance.get<{ url: string }>(`${base}/connect`)).data;
      window.location.assign(url);
      return [];
    }
    throw error;
  }

  await loadPicker();
  const picker = window.google!.picker;

  const builder = new picker.PickerBuilder();
  if (!folder) builder.enableFeature(picker.Feature.MULTISELECT_ENABLED);

  return new Promise((resolve) => {
    builder
      .setDeveloperKey(config.api_key)
      .setAppId(config.app_id)
      .setOAuthToken(config.access_token)
      .addView(
        folder
          ? new picker.DocsView(picker.ViewId.FOLDERS).setSelectFolderEnabled(true)
          : new picker.DocsView(picker.ViewId.DOCS).setMimeTypes(PICKER_MIME_TYPES),
      )
      .setCallback((data: { action: string; docs?: DriveDoc[] }) => {
        if (data.action === picker.Action.PICKED) resolve(data.docs ?? []);
        if (data.action === picker.Action.CANCEL) resolve([]);
      })
      .build()
      .setVisible(true);
  });
}

export function useImportDriveFiles() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (files: { id: string; accessLevel: AccessLevel }[]) =>
      (
        await axiosInstance.post<StoredFile[]>("/integrations/google/files", {
          files: files.map(({ id, accessLevel }) => ({ id, access_level: accessLevel })),
        })
      ).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["files", "list"] }),
  });
}

export type DriveSyncUpdate = {
  folder_id: string;
  folder_name: string;
  access_level: AccessLevel;
  timezone: string;
  sync_time: string;
};

export type DriveSyncSettings = DriveSyncUpdate & {
  owner_email: string;
  run_requested: boolean;
  last_synced_at: string | null;
  last_result: string | null;
};

const DRIVE_SYNC_KEY = ["admin", "drive-sync"];

// `null` when no folder is synced.
export const useDriveSync = (enabled: boolean) =>
  useQuery({
    queryKey: DRIVE_SYNC_KEY,
    enabled,
    queryFn: async ({ signal }) =>
      (await axiosInstance.get<DriveSyncSettings | null>("/integrations/google/sync", { signal }))
        .data,
    // While a run is waiting for the worker, check back until its result lands.
    refetchInterval: (query) => (query.state.data?.run_requested ? 10_000 : false),
  });

export const useSaveDriveSync = () => {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (data: DriveSyncUpdate) =>
      (await axiosInstance.put<DriveSyncSettings>("/integrations/google/sync", data)).data,
    onSuccess: (data) => client.setQueryData(DRIVE_SYNC_KEY, data),
  });
};

export const useRunDriveSync = () => {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      await axiosInstance.post("/integrations/google/sync/run");
    },
    onSuccess: () => client.invalidateQueries({ queryKey: DRIVE_SYNC_KEY }),
  });
};

export const useStopDriveSync = () => {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      await axiosInstance.delete("/integrations/google/sync");
    },
    onSuccess: () => client.setQueryData(DRIVE_SYNC_KEY, null),
  });
};
