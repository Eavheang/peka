import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { LoginRequest, UserResponse } from "@/interface/auth";
import axiosInstance from "@/utils/axios";

export const useListUsers = () =>
  useQuery<UserResponse[]>({
    queryKey: ["users", "list"],
    queryFn: async () => (await axiosInstance.get<UserResponse[]>("/auth/users")).data,
  });

export const useUpdateUserActivation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, is_active }: Pick<UserResponse, "id" | "is_active">) =>
      (await axiosInstance.patch<UserResponse>(`/auth/users/${id}`, { is_active })).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users", "list"] }),
  });
};

export const useCreateUser = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: LoginRequest & { role: UserResponse["role"] }) =>
      (await axiosInstance.post<UserResponse>("/auth/users", data)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users", "list"] }),
  });
};

export const useDeleteUser = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => axiosInstance.delete(`/auth/users/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users", "list"] }),
  });
};
