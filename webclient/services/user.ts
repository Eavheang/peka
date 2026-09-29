import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type {
  InvitationResponse,
  InvitationSummary,
  UserResponse,
  UserRole,
} from "@/interface/auth";
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

export const useUpdateUserRole = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, role }: Pick<UserResponse, "id" | "role">) =>
      (await axiosInstance.patch<UserResponse>(`/auth/users/${id}/role`, { role })).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users", "list"] }),
  });
};

export const useListInvitations = () =>
  useQuery<InvitationSummary[]>({
    queryKey: ["users", "invitations"],
    queryFn: async () => (await axiosInstance.get<InvitationSummary[]>("/auth/invitations")).data,
  });

export const useInviteUser = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: { email: string; role: UserRole }) =>
      (await axiosInstance.post<InvitationResponse>("/auth/invitations", data)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users", "invitations"] }),
  });
};

export const useResendInvitation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) =>
      (await axiosInstance.post<InvitationResponse>(`/auth/invitations/${id}/resend`)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users", "invitations"] }),
  });
};

export const useRevokeInvitation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => axiosInstance.delete(`/auth/invitations/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users", "invitations"] }),
  });
};

export const useDeleteUser = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => axiosInstance.delete(`/auth/users/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users", "list"] }),
  });
};
