import { useQuery } from "@tanstack/react-query";

import type { ChatRequest, ChatResponse, Conversation, ConversationDetail } from "@/interface/chat";
import axiosInstance from "@/utils/axios";

export async function sendChatMessage(request: ChatRequest): Promise<ChatResponse> {
  const response = await axiosInstance.post<ChatResponse>("/chat", request);
  return response.data;
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
