import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import axiosInstance from "@/utils/axios";

export type ProviderSettings = {
  llm_base_url: string;
  llm_model: string;
  llm_configured: boolean;
  exa_base_url: string;
  exa_configured: boolean;
};

export type ProviderSettingsUpdate = {
  llm_base_url: string;
  llm_model: string;
  llm_api_key?: string;
  exa_base_url: string;
  exa_api_key?: string;
};

export const useProviderSettings = () =>
  useQuery({
    queryKey: ["admin", "provider-settings"],
    queryFn: async () =>
      (await axiosInstance.get<ProviderSettings>("/admin/settings/providers")).data,
  });

export const useSaveProviderSettings = () => {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (data: ProviderSettingsUpdate) =>
      (await axiosInstance.put<ProviderSettings>("/admin/settings/providers", data)).data,
    onSuccess: (data) => client.setQueryData(["admin", "provider-settings"], data),
  });
};

export const useTestProvider = () =>
  useMutation({
    mutationFn: async (provider: "llm" | "exa") =>
      (
        await axiosInstance.post<{ ok: boolean; status: number | null; message: string }>(
          `/admin/settings/providers/test/${provider}`,
        )
      ).data,
  });
