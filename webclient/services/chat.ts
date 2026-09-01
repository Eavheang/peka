import type { ChatRequest, ChatResponse } from "@/interface/chat";
import axiosInstance from "@/utils/axios";

export async function sendChatMessage(request: ChatRequest): Promise<ChatResponse> {
  const response = await axiosInstance.post<ChatResponse>("/chat", request);
  return response.data;
}
