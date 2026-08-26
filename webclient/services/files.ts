"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { StoredFile } from "@/interface/files";
import axiosInstance from "@/utils/axios";

const filesKey = ["files", "list"];

export function useListFiles() {
  return useQuery<StoredFile[]>({
    queryKey: filesKey,
    queryFn: async () => (await axiosInstance.get<StoredFile[]>("/files")).data,
    refetchInterval: (query) =>
      query.state.data?.some(
        (file) => file.okf_status === "queued" || file.okf_status === "processing",
      )
        ? 3000
        : false,
  });
}

export function useUploadFiles() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (files: File[]) => {
      const formData = new FormData();
      files.forEach((file) => formData.append("files", file));
      return (await axiosInstance.post<StoredFile[]>("/files", formData)).data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: filesKey }),
  });
}

export function useRetryFile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) =>
      (await axiosInstance.post<StoredFile>(`/files/${id}/retry-okf`)).data,
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
