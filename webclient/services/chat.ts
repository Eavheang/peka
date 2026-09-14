import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { ChatRequest, ChatResponse, Citation, Conversation, ConversationDetail, SourcePreviewResponse } from "@/interface/chat";
import axiosInstance from "@/utils/axios";

export async function sendChatMessage(request: ChatRequest): Promise<ChatResponse> {
  const response = await axiosInstance.post<ChatResponse>("/chat", request);
  return response.data;
}

export function useSourcePreview(citation: Citation) {
  return useQuery<SourcePreviewResponse>({
    queryKey: ["chat", "source-preview", citation.chunk_id, citation.title, citation.heading],
    queryFn: async ({ signal }) => (
      await axiosInstance.post<SourcePreviewResponse>("/chat/source-preview", {
        chunk_id: citation.chunk_id,
        title: citation.title,
        heading: citation.heading,
      }, { signal })
    ).data,
    retry: false,
    refetchOnMount: false,
  });
}

export async function listConversations(): Promise<Conversation[]> {
  const response = await axiosInstance.get<Conversation[]>("/chat/conversations");
  return response.data;
}

export async function getConversation(conversationId: string): Promise<ConversationDetail> {
  const response = await axiosInstance.get<ConversationDetail>(
    `/chat/conversations/${conversationId}`,
  );
  return response.data;
}

export async function deleteConversation(conversationId: string): Promise<void> {
  await axiosInstance.delete(`/chat/conversations/${conversationId}`);
}

export function useListConversations(enabled = true) {
  return useQuery<Conversation[]>({
    queryKey: ["chat", "conversations"],
    enabled,
    staleTime: 30 * 1000,
    queryFn: listConversations,
  });
}

export function useGetConversation(conversationId?: string) {
  return useQuery<ConversationDetail>({
    queryKey: ["chat", "conversations", conversationId],
    enabled: Boolean(conversationId),
    queryFn: () => getConversation(conversationId as string),
  });
}

export function useDeleteConversation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deleteConversation,
    onSuccess: (_data, conversationId) => {
      queryClient.removeQueries({ queryKey: ["chat", "conversations", conversationId] });
      queryClient.invalidateQueries({ queryKey: ["chat", "conversations"] });
    },
  });
}
