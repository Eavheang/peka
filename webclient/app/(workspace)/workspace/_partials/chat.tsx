"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowUp, BookOpen, LoaderCircle } from "lucide-react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import type { ChatResult, ChatUIMessage } from "@/interface/chat";
import { sendChatMessage, useGetConversation } from "@/services/chat";

const MAX_QUERY_LENGTH = 4000;

export function ChatPanel({ conversationId }: { conversationId?: string }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  const [validationError, setValidationError] = useState("");
  const [messages, setMessages] = useState<ChatUIMessage[]>([]);
  const [isPending, setIsPending] = useState(false);
  const [requestError, setRequestError] = useState("");
  const conversationRef = useRef<HTMLDivElement>(null);
  const queryInputRef = useRef<HTMLTextAreaElement>(null);
  const shouldAutoScroll = useRef(true);
  const conversationQuery = useGetConversation(conversationId);

  useEffect(() => {
    setMessages([]);
  }, [conversationId]);

  useEffect(() => {
    if (!conversationQuery.data) return;

    setMessages(
      conversationQuery.data.messages.map((message) => toChatUIMessage(message, conversationId)),
    );
  }, [conversationQuery.data, conversationId]);

  useEffect(() => {
    const conversation = conversationRef.current;
    if (!conversation || !shouldAutoScroll.current) return;

    conversation.scrollTo({ top: conversation.scrollHeight, behavior: "auto" });
  }, [messages]);

  useEffect(() => {
    const queryInput = queryInputRef.current;
    if (!queryInput) return;

    queryInput.style.height = "auto";
    queryInput.style.height = `${queryInput.scrollHeight}px`;
  }, [query]);

  const trimmedQuery = query.trim();

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!trimmedQuery) {
      setValidationError("Ask a question to start a conversation.");
      return;
    }
    if (trimmedQuery.length > MAX_QUERY_LENGTH) {
      setValidationError(
        `Questions must be ${MAX_QUERY_LENGTH.toLocaleString()} characters or fewer.`,
      );
      return;
    }

    setValidationError("");
    setRequestError("");
    const userMessage: ChatUIMessage = {
      id: crypto.randomUUID(),
      role: "user",
      parts: [{ type: "text", text: trimmedQuery }],
    };
    setMessages((current) => [...current, userMessage]);
    setIsPending(true);
    setQuery("");

    try {
      const response = await sendChatMessage({
        query: trimmedQuery,
        ...(conversationId ? { conversation_id: conversationId } : {}),
      });

      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          parts: [
            { type: "text", text: response.answer },
            {
              type: "data-chat-result",
              data: {
                conversationId: response.conversation_id,
                refused: response.refused,
                citations: response.citations,
              },
            },
          ],
        },
      ]);
      queryClient.invalidateQueries({ queryKey: ["chat", "conversations"] });
      if (!conversationId) router.replace(`/workspace/${response.conversation_id}`);
    } catch {
      setQuery((currentQuery) => currentQuery || trimmedQuery);
      setRequestError("We could not save that conversation. Please try again.");
    } finally {
      setIsPending(false);
    }
  }

  return (
    <section className="relative h-full min-h-0 w-full px-4 sm:px-6">
      <div
        ref={conversationRef}
        aria-live="polite"
        className="absolute inset-0 overflow-y-auto"
        onScroll={(event) => {
          const conversation = event.currentTarget;
          shouldAutoScroll.current =
            conversation.scrollHeight - conversation.scrollTop - conversation.clientHeight < 80;
        }}
      >
        <div className="mx-auto flex min-h-full w-full max-w-3xl flex-col gap-8 px-4 pb-56 pt-8 sm:px-0">
          {conversationId && conversationQuery.isPending ? (
            <div className="flex flex-1 items-center justify-center py-16 text-sm text-muted">
              <LoaderCircle aria-hidden="true" className="mr-2 animate-spin" size={16} />
              Loading conversation...
            </div>
          ) : conversationId && conversationQuery.isError ? (
            <p className="flex flex-1 items-center justify-center py-16 text-sm text-danger">
              We could not load this conversation.
            </p>
          ) : messages.length === 0 ? (
            <div className="flex min-h-full flex-col items-center justify-center py-16 text-center">
              <div className="mb-5 flex size-14 items-center justify-center rounded-2xl border border-border bg-secondary text-primary">
                <BookOpen aria-hidden="true" size={24} />
              </div>
              <h1 className="text-3xl tracking-tight sm:text-4xl">What can I help you find?</h1>
              <p className="mt-3 max-w-md text-sm leading-6 text-copy">
                Ask about a policy, project, or document in your library. Peka answers using the
                knowledge you have indexed.
              </p>
            </div>
          ) : (
            messages.map((message) => (
              <ChatMessageBubble
                key={message.id}
                message={message}
                result={getChatResult(message)}
              />
            ))
          )}
        </div>
      </div>

      <form
        className="absolute inset-x-0 bottom-0 z-20 bg-background px-4 pb-4 pt-3 sm:px-0"
        onSubmit={handleSubmit}
      >
        <div className="mx-auto max-w-3xl">
          <label className="sr-only" htmlFor="chat-question">
            Your question
          </label>
          <div className="flex items-end gap-2 rounded-2xl border border-border bg-white/70 p-2 shadow-[0_8px_30px_rgb(24_26_25/8%)] transition-shadow focus-within:border-primary/60 focus-within:shadow-[0_8px_30px_rgb(24_26_25/12%)]">
            <textarea
              aria-describedby="chat-question-help"
              className="max-h-48 min-h-10 min-w-0 flex-1 resize-none overflow-y-auto bg-transparent px-3 py-2 text-sm leading-6 text-foreground outline-none placeholder:text-muted"
              id="chat-question"
              maxLength={MAX_QUERY_LENGTH + 100}
              name="question"
              placeholder="Message Peka..."
              ref={queryInputRef}
              rows={1}
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                if (validationError) setValidationError("");
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }}
            />
            <Button
              aria-label={isPending ? "Searching" : "Send message"}
              className="rounded-full"
              disabled={isPending || conversationQuery.isPending || conversationQuery.isError}
              size="icon-lg"
              type="submit"
            >
              {isPending ? (
                <LoaderCircle aria-hidden="true" className="animate-spin" />
              ) : (
                <ArrowUp aria-hidden="true" />
              )}
            </Button>
          </div>
          <p id="chat-question-help" className="sr-only">
            Press Enter to send or Shift + Enter for a new line.
          </p>
          {(validationError || requestError) && (
            <p className="mt-2 text-sm text-danger" role="alert">
              {validationError || "We could not save that conversation. Please try again."}
            </p>
          )}
          <p className="mt-2 text-center text-[11px] text-muted">
            Peka can make mistakes. Check important details against the source.
          </p>
        </div>
      </form>
    </section>
  );
}

function ChatMessageBubble({ message, result }: { message: ChatUIMessage; result?: ChatResult }) {
  const isUser = message.role === "user";

  return (
    <article className={isUser ? "ml-auto max-w-2xl" : "max-w-3xl"}>
      <div
        className={
          isUser
            ? "rounded-2xl rounded-tr-sm bg-panel px-5 py-4 text-panel-foreground"
            : "text-foreground"
        }
      >
        {result?.refused && (
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-primary">
            Not enough evidence
          </p>
        )}
        {message.parts.map(
          (part, index) =>
            part.type === "text" && (
              <p
                className={
                  isUser
                    ? "whitespace-pre-wrap text-sm leading-7 text-panel-foreground"
                    : "whitespace-pre-wrap text-sm leading-7"
                }
                key={`${message.id}-text-${index}`}
              >
                {part.text}
              </p>
            ),
        )}
        {!isUser && result && result.citations.length > 0 && (
          <div className="mt-5 border-t border-border pt-4">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">
              Sources
            </p>
            <ul className="space-y-2">
              {result.citations.map((citation, index) => (
                <li
                  className="text-xs text-copy"
                  key={`${citation.title}-${citation.heading}-${index}`}
                >
                  <span className="font-medium text-foreground">
                    [{index + 1}] {citation.title}
                  </span>
                  {citation.heading && ` · ${citation.heading}`}
                  {citation.page !== null && ` · p. ${citation.page}`}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </article>
  );
}

function getChatResult(message: ChatUIMessage): ChatResult | undefined {
  const part = message.parts.find((candidate) => candidate.type === "data-chat-result");
  return part?.type === "data-chat-result" ? part.data : undefined;
}

function toChatUIMessage(
  message: {
    id: string;
    role: "user" | "assistant";
    content: string;
    refused: boolean;
    citations: ChatResult["citations"];
  },
  conversationId?: string,
): ChatUIMessage {
  return {
    id: message.id,
    role: message.role,
    parts: [
      { type: "text", text: message.content },
      ...(message.role === "assistant"
        ? [
            {
              type: "data-chat-result" as const,
              data: {
                conversationId: conversationId ?? "",
                refused: message.refused,
                citations: message.citations,
              },
            },
          ]
        : []),
    ],
  };
}
