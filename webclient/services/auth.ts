import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { LoginRequest, TokenResponse, UserResponse } from "@/interface/auth";
import axiosInstance from "@/utils/axios";

export const useLogin = () => {
  return useMutation({
    mutationFn: async (credentials: LoginRequest) => {
      const response = await axiosInstance.post<TokenResponse>("/auth/login", credentials);
      return response.data;
    },
  });
};

export const useGetCurrentUser = (accessToken: string) => {
  return useQuery<UserResponse>({
    queryKey: ["users", "me"],
    enabled: Boolean(accessToken),
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    queryFn: async () => {
      const response = await axiosInstance.get<UserResponse>("/auth/me", {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      return response.data;
    },
  });
};

export const useLogout = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (accessToken: string) => {
      await axiosInstance.post("/auth/logout", undefined, {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
    },
    onSuccess: async () => {
      await queryClient.removeQueries({ queryKey: ["users", "me"] });
    },
  });
};

export const useUpdateProfile = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: { display_name: string }) =>
      (await axiosInstance.patch<UserResponse>('/auth/me', data)).data,
    onSuccess: (user) => queryClient.setQueryData(['users', 'me'], user),
  });
};

export const useChangePassword = () =>
  useMutation({
    mutationFn: async (data: { current_password: string; new_password: string }) => {
      await axiosInstance.post('/auth/password', data);
    },
  });
