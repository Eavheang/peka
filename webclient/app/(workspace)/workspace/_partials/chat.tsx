"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { ArrowUp, BookOpen, Globe2, LoaderCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { Button } from "@/components/ui/button";
import type { ChatMessage, ChatResult } from "@/interface/chat";
import { sendChatMessageStream, useGetConversation } from "@/services/chat";

const MAX_QUERY_LENGTH = 4000;
const WEB_SEARCH_STORAGE_KEY = "peka_web_search_enabled";
const SourcePreview = dynamic(() =>
  import("./sourcePreview").then((module) => module.SourcePreview),
);

type DisplayMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  result?: ChatResult;
};

export function ChatPanel({ conversationId }: { conversationId?: string }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  const [validationError, setValidationError] = useState("");
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [isPending, setIsPending] = useState(false);
  const [requestError, setRequestError] = useState("");
  const [streamStatus, setStreamStatus] = useState("");
  const [streamingMessageId, setStreamingMessageId] = useState<string>();
  const [webSearchEnabled, setWebSearchEnabled] = useState(false);
  const conversationRef = useRef<HTMLDivElement>(null);
  const queryInputRef = useRef<HTMLTextAreaElement>(null);
  const shouldAutoScroll = useRef(true);
  const conversationQuery = useGetConversation(conversationId);

  useEffect(() => {
    setWebSearchEnabled(window.localStorage.getItem(WEB_SEARCH_STORAGE_KEY) === "true");
  }, []);

  useEffect(() => {
    setMessages([]);
  }, [conversationId]);

  useEffect(() => {
    if (!conversationQuery.data) return;

    setMessages(
      conversationQuery.data.messages.map((message) => toDisplayMessage(message, conversationId)),
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
    if (isPending) return;
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
    const userMessage: DisplayMessage = {
      id: crypto.randomUUID(),
      role: "user",
      text: trimmedQuery,
    };
    const assistantMessageId = crypto.randomUUID();
    setMessages((current) => [
      ...current,
      userMessage,
      { id: assistantMessageId, role: "assistant", text: "" },
    ]);
    setIsPending(true);
    setStreamingMessageId(assistantMessageId);
    setStreamStatus("Thinking...");
    setQuery("");

    try {
      const response = await sendChatMessageStream(
        {
          query: trimmedQuery,
          ...(conversationId ? { conversation_id: conversationId } : {}),
          web_search: webSearchEnabled,
        },
        (event) => {
          if (event.type === "status") {
            setStreamStatus(event.message);
            return;
          }
          setMessages((current) =>
            current.map((message) =>
              message.id === assistantMessageId
                ? { ...message, text: message.text + event.delta }
                : message,
            ),
          );
        },
      );

      setMessages((current) =>
        current.map((message) =>
          message.id === assistantMessageId
            ? {
                ...message,
                text: response.answer,
                result: {
                  conversationId: response.conversation_id,
                  refused: response.refused,
                  citations: response.citations,
                },
              }
            : message,
        ),
      );
      queryClient.invalidateQueries({ queryKey: ["chat", "conversations"] });
      if (!conversationId) router.replace(`/workspace/${response.conversation_id}`);
    } catch (error: unknown) {
      setMessages((current) => current.filter((message) => message.id !== assistantMessageId));
      setQuery((currentQuery) => currentQuery || trimmedQuery);
      const detail = axios.isAxiosError(error)
        ? error.response?.data?.detail
        : error instanceof Error
          ? error.message
          : undefined;
      setRequestError(
        typeof detail === "string"
          ? detail
          : "We could not save that conversation. Please try again.",
      );
    } finally {
      setIsPending(false);
      setStreamingMessageId(undefined);
      setStreamStatus("");
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
                Ask a question or explore a document in your library. Peka searches your indexed
                knowledge when needed.
              </p>
            </div>
          ) : (
            messages.map((message) => (
              <ChatMessageBubble
                key={message.id}
                message={message}
                streamingStatus={message.id === streamingMessageId ? streamStatus : undefined}
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
            <div className="flex min-w-0 flex-1 flex-col">
              <textarea
                aria-describedby="chat-question-help"
                className="max-h-48 min-h-10 min-w-0 resize-none overflow-y-auto bg-transparent px-3 py-2 text-sm leading-6 text-foreground outline-none placeholder:text-muted"
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
              <div className="flex items-center gap-3 px-3 pb-1 pt-2">
                <label className="inline-flex cursor-pointer items-center gap-2 text-xs font-medium text-copy">
                  <input
                    aria-describedby="web-search-help"
                    aria-label="Allow web search"
                    checked={webSearchEnabled}
                    className="peer sr-only"
                    role="switch"
                    type="checkbox"
                    onChange={(event) => {
                      const enabled = event.target.checked;
                      setWebSearchEnabled(enabled);
                      window.localStorage.setItem(WEB_SEARCH_STORAGE_KEY, String(enabled));
                    }}
                  />
                  <Globe2 aria-hidden="true" size={14} />
                  Allow web search
                  <span
                    aria-hidden="true"
                    className="relative h-5 w-9 rounded-full bg-border transition-colors after:absolute after:top-0.5 after:left-0.5 after:size-4 after:rounded-full after:bg-white after:shadow-sm after:transition-transform peer-checked:bg-primary peer-checked:after:translate-x-4 peer-focus-visible:ring-2 peer-focus-visible:ring-ring/50"
                  />
                </label>
                <span id="web-search-help" className="text-[11px] text-muted">
                  {webSearchEnabled ? "Public web enabled" : "Private knowledge only"}
                </span>
              </div>
            </div>
            <Button
              aria-label={isPending ? "Responding" : "Send message"}
              className="rounded-full"
              disabled={isPending}
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
              {validationError || requestError}
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

function ChatMessageBubble({
  message,
  streamingStatus,
}: {
  message: DisplayMessage;
  streamingStatus?: string;
}) {
  const isUser = message.role === "user";
  const result = message.result;

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
        {message.text &&
          (isUser ? (
            <p className="whitespace-pre-wrap text-sm leading-7 text-panel-foreground">
              {message.text}
            </p>
          ) : (
            <div className="break-words text-sm leading-7 [&_h1]:my-4 [&_h1]:text-xl [&_h2]:my-4 [&_h2]:text-lg [&_h3]:my-3 [&_h3]:text-base [&_p]:my-3 [&_ul]:my-3 [&_ul]:list-disc [&_ul]:pl-6 [&_ol]:my-3 [&_ol]:list-decimal [&_ol]:pl-6 [&_li]:my-1 [&_pre]:my-3 [&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:bg-secondary [&_pre]:p-3 [&_code]:text-xs">
              <Markdown remarkPlugins={[remarkGfm]} skipHtml>
                {message.text}
              </Markdown>
            </div>
          ))}
        {streamingStatus && !message.text && (
          <p className="flex items-center gap-2 text-sm text-muted">
            <LoaderCircle aria-hidden="true" className="animate-spin" size={14} />
            {streamingStatus}
          </p>
        )}
        {!isUser && result && result.citations.length > 0 && (
          <details className="mt-5 border-t border-border pt-4">
            <summary className="cursor-pointer text-xs font-semibold text-muted hover:text-foreground">
              Sources ({result.citations.length})
            </summary>
            <ul className="mt-3 flex flex-col gap-2">
              {result.citations.map((citation, index) => (
                <li
                  className="text-xs text-copy"
                  key={`${citation.title}-${citation.heading}-${index}`}
                >
                  <SourcePreview citation={citation} number={index + 1} />
                </li>
              ))}
            </ul>
          </details>
        )}
      </div>
    </article>
  );
}

function toDisplayMessage(
  message: Pick<ChatMessage, "id" | "role" | "content" | "refused" | "citations">,
  conversationId?: string,
): DisplayMessage {
  return {
    id: message.id,
    role: message.role,
    text: message.content,
    ...(message.role === "assistant"
      ? {
          result: {
            conversationId: conversationId ?? "",
            refused: message.refused,
            citations: message.citations,
          },
        }
      : {}),
  };
}
