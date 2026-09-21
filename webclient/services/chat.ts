import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type {
  ChatRequest,
  ChatResponse,
  Citation,
  Conversation,
  ConversationDetail,
  SourcePreviewResponse,
} from "@/interface/chat";
import axiosInstance, { fetchAuthenticated } from "@/utils/axios";

type ChatStreamUpdate = { type: "status"; message: string } | { type: "text"; delta: string };

type ChatStreamEvent =
  | ChatStreamUpdate
  | { type: "done"; response: ChatResponse }
  | { type: "error"; message: string };

export async function sendChatMessageStream(
  request: ChatRequest,
  onUpdate: (update: ChatStreamUpdate) => void,
  signal?: AbortSignal,
): Promise<ChatResponse> {
  const response = await fetchAuthenticated(
    `${process.env.NEXT_PUBLIC_API_URL ?? ""}/chat/stream`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
      signal,
    },
  );

  if (!response.ok) {
    let detail: string | undefined;
    try {
      const body = (await response.json()) as unknown;
      if (isRecord(body) && typeof body.detail === "string") detail = body.detail;
    } catch {
      // Use the generic message below when the server did not return JSON.
    }
    throw new Error(detail ?? "We could not save that conversation. Please try again.");
  }
  if (!response.body) throw new Error("The response stream is unavailable.");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let completedResponse: ChatResponse | undefined;

  const handleLine = (line: string) => {
    if (!line.startsWith("data:")) return;
    const payload = line.slice(5).trimStart();
    if (payload === "[DONE]") return;

    let parsed: unknown;
    try {
      parsed = JSON.parse(payload);
    } catch {
      return;
    }
    const event = parseChatStreamEvent(parsed);
    if (!event) return;
    if (event.type === "error") throw new Error(event.message);
    if (event.type === "done") {
      completedResponse = event.response;
      return;
    }
    onUpdate(event);
  };

  try {
    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      let newlineIndex = buffer.indexOf("\n");
      while (newlineIndex >= 0) {
        const line = buffer.slice(0, newlineIndex).replace(/\r$/, "");
        buffer = buffer.slice(newlineIndex + 1);
        handleLine(line);
        newlineIndex = buffer.indexOf("\n");
      }
      if (done) break;
    }
    if (buffer.trim()) handleLine(buffer.trim());
  } finally {
    reader.releaseLock();
  }

  if (!completedResponse) throw new Error("The response stream ended before completion.");
  return completedResponse;
}

function parseChatStreamEvent(value: unknown): ChatStreamEvent | undefined {
  if (!isRecord(value) || typeof value.type !== "string") return undefined;
  if (value.type === "status" && typeof value.message === "string") {
    return { type: "status", message: value.message };
  }
  if (value.type === "text" && typeof value.delta === "string") {
    return { type: "text", delta: value.delta };
  }
  if (value.type === "error" && typeof value.message === "string") {
    return { type: "error", message: value.message };
  }
  if (value.type === "done" && isChatResponse(value.response)) {
    return { type: "done", response: value.response };
  }
  return undefined;
}

function isChatResponse(value: unknown): value is ChatResponse {
  return (
    isRecord(value) &&
    typeof value.answer === "string" &&
    typeof value.refused === "boolean" &&
    Array.isArray(value.citations) &&
    typeof value.conversation_id === "string" &&
    Array.isArray(value.messages)
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function useSourcePreview(citation: Citation) {
  return useQuery<SourcePreviewResponse>({
    queryKey: ["chat", "source-preview", citation.chunk_id, citation.title, citation.heading],
    queryFn: async ({ signal }) =>
      (
        await axiosInstance.post<SourcePreviewResponse>(
          "/chat/source-preview",
          {
            chunk_id: citation.chunk_id,
            title: citation.title,
            heading: citation.heading,
          },
          { signal },
        )
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
