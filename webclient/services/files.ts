"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { AccessLevel, StoredFile } from "@/interface/files";
import axiosInstance from "@/utils/axios";

const filesKey = ["files", "list"];

export function useListFiles() {
  return useQuery<StoredFile[]>({
    queryKey: filesKey,
    queryFn: async () => (await axiosInstance.get<StoredFile[]>("/files")).data,
    refetchInterval: (query) =>
      query.state.data?.some(
        (file) => file.index_status === "queued" || file.index_status === "processing",
      )
        ? 3000
        : false,
  });
}

export function useUploadFiles() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (uploads: { file: File; accessLevel: AccessLevel }[]) => {
      const formData = new FormData();
      uploads.forEach(({ file, accessLevel }) => {
        formData.append("files", file);
        formData.append("access_levels", accessLevel);
      });
      return (await axiosInstance.post<StoredFile[]>("/files", formData)).data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: filesKey }),
  });
}

export function useRetryFile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) =>
      (await axiosInstance.post<StoredFile>(`/files/${id}/retry-indexing`)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: filesKey }),
  });
}

export function useUpdateFileAccessLevel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, accessLevel }: { id: string; accessLevel: AccessLevel }) =>
      (
        await axiosInstance.patch<StoredFile>(`/files/${id}/access-level`, {
          access_level: accessLevel,
        })
      ).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: filesKey }),
  });
}

export function useDeleteFile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => axiosInstance.delete(`/files/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: filesKey }),
  });
}

export async function downloadFile(file: StoredFile) {
  const response = await axiosInstance.get<Blob>(`/files/${file.id}`, { responseType: "blob" });
  const url = URL.createObjectURL(response.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = file.path.split("/").pop() ?? "download";
  link.click();
  URL.revokeObjectURL(url);
}
