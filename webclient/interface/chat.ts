export interface Citation {
  title: string;
  heading: string;
  page: number | null;
  source_locations: Record<string, unknown>[];
}

export interface ChatRequest {
  query: string;
  conversation_id?: string;
}

export interface ChatResponse {
  answer: string;
  refused: boolean;
  citations: Citation[];
  conversation_id: string;
  messages: ChatMessage[];
}

export interface ChatResult {
  conversationId: string;
  refused: boolean;
  citations: Citation[];
}

export type ChatMessagePart =
  | { type: "text"; text: string }
  | { type: "data-chat-result"; data: ChatResult };

export interface ChatUIMessage {
  id: string;
  role: "user" | "assistant";
  parts: ChatMessagePart[];
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  refused: boolean;
  citations: Citation[];
  status: "completed";
  created_at: string;
}

export interface Conversation {
  id: string;
  owner_id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ConversationDetail extends Conversation {
  messages: ChatMessage[];
}
