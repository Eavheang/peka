"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  ArrowDown,
  ArrowUp,
  BookOpen,
  Check,
  Copy,
  Globe2,
  LoaderCircle,
  RotateCcw,
  Square,
} from "lucide-react";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { ChatMessage, ChatResult } from "@/interface/chat";
import { sendChatMessageStream, useGetConversation } from "@/services/chat";
import { getApiErrorMessage } from "@/utils/api-error";

const MAX_QUERY_LENGTH = 4000;
const WEB_SEARCH_STORAGE_KEY = "peka_web_search_enabled";
const SourcePreview = dynamic(() =>
  import("./sourcePreview").then((module) => module.SourcePreview),
);

const EXAMPLE_QUESTIONS = [
  "Summarize the key points of our onboarding documents",
  "What is our leave policy?",
  "Which documents mention security requirements?",
];

type DisplayMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  result?: ChatResult;
  // "stopped": the user stopped the answer. "failed": the stream broke; `question` is retried.
  state?: "stopped" | "failed";
  error?: string;
  question?: string;
};

export function ChatPanel({ conversationId }: { conversationId?: string }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  const [validationError, setValidationError] = useState("");
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [isPending, setIsPending] = useState(false);
  const [streamStatus, setStreamStatus] = useState("");
  const [announcement, setAnnouncement] = useState("");
  const [streamingMessageId, setStreamingMessageId] = useState<string>();
  const [showJumpToLatest, setShowJumpToLatest] = useState(false);
  const [webSearchEnabled, setWebSearchEnabled] = useState(false);
  const conversationRef = useRef<HTMLDivElement>(null);
  const queryInputRef = useRef<HTMLTextAreaElement>(null);
  const shouldAutoScroll = useRef(true);
  const pendingStreamDelta = useRef("");
  const streamFrame = useRef<number | null>(null);
  const skipNextConversationLoad = useRef<string | false>(false);
  const streamAbort = useRef<AbortController | null>(null);
  const conversationQuery = useGetConversation(conversationId);

  useEffect(() => {
    return () => {
      if (streamFrame.current !== null) cancelAnimationFrame(streamFrame.current);
      streamAbort.current?.abort();
    };
  }, []);

  useEffect(() => {
    setWebSearchEnabled(window.localStorage.getItem(WEB_SEARCH_STORAGE_KEY) === "true");
  }, []);

  useEffect(() => {
    if (conversationId && conversationId === skipNextConversationLoad.current) return;
    skipNextConversationLoad.current = false;
    setMessages(
      conversationQuery.data?.messages.map((message) =>
        toDisplayMessage(message, conversationId),
      ) ?? [],
    );
  }, [conversationId, conversationQuery.data]);

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

  function appendStreamDelta(messageId: string, delta: string) {
    setMessages((current) =>
      current.map((message) =>
        message.id === messageId ? { ...message, text: message.text + delta } : message,
      ),
    );
  }

  function flushStreamDelta(messageId: string) {
    if (streamFrame.current !== null) {
      cancelAnimationFrame(streamFrame.current);
      streamFrame.current = null;
    }

    const delta = pendingStreamDelta.current;
    pendingStreamDelta.current = "";
    if (delta) appendStreamDelta(messageId, delta);
  }

  function queueStreamDelta(messageId: string, delta: string) {
    pendingStreamDelta.current += delta;
    if (streamFrame.current === null) {
      streamFrame.current = requestAnimationFrame(() => flushStreamDelta(messageId));
    }
  }

  function discardStreamDelta() {
    if (streamFrame.current !== null) {
      cancelAnimationFrame(streamFrame.current);
      streamFrame.current = null;
    }
    pendingStreamDelta.current = "";
  }

  function setAssistantMessage(messageId: string, update: Partial<DisplayMessage>) {
    setMessages((current) =>
      current.map((message) => (message.id === messageId ? { ...message, ...update } : message)),
    );
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
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
    setQuery("");
    void askQuestion(trimmedQuery);
  }

  function handleRetry(failedMessageId: string, question: string) {
    // Drop the failed answer and the question before it; askQuestion adds both back.
    setMessages((current) => {
      const index = current.findIndex((message) => message.id === failedMessageId);
      return index < 1 ? current : [...current.slice(0, index - 1), ...current.slice(index + 1)];
    });
    void askQuestion(question);
  }

  async function askQuestion(question: string) {
    if (isPending) return;
    setValidationError("");
    shouldAutoScroll.current = true;
    setShowJumpToLatest(false);
    const userMessage: DisplayMessage = {
      id: crypto.randomUUID(),
      role: "user",
      text: question,
    };
    const assistantMessageId = crypto.randomUUID();
    setMessages((current) => [
      ...current,
      userMessage,
      { id: assistantMessageId, role: "assistant", text: "" },
    ]);
    // Pick the id of a new conversation here so a stopped answer can still be opened.
    const newConversationId = conversationId ? undefined : crypto.randomUUID();
    const abort = new AbortController();
    streamAbort.current = abort;
    let shownText = "";
    pendingStreamDelta.current = "";
    setIsPending(true);
    setStreamingMessageId(assistantMessageId);
    setStreamStatus("Thinking...");
    setAnnouncement("Thinking...");

    try {
      const response = await sendChatMessageStream(
        {
          query: question,
          ...(conversationId
            ? { conversation_id: conversationId }
            : { new_conversation_id: newConversationId }),
          web_search: webSearchEnabled,
        },
        (event) => {
          if (event.type === "status") {
            setStreamStatus(event.message);
            setAnnouncement(event.message);
          } else if (event.type === "reset") {
            discardStreamDelta();
            shownText = "";
            setAssistantMessage(assistantMessageId, { text: "" });
          } else {
            shownText += event.delta;
            queueStreamDelta(assistantMessageId, event.delta);
          }
        },
        abort.signal,
      );

      // The saved answer is the source of truth; replace whatever was streamed with it.
      discardStreamDelta();
      setAssistantMessage(assistantMessageId, {
        text: response.answer,
        result: {
          conversationId: response.conversation_id,
          refused: response.refused,
          citations: response.citations,
        },
      });
      setAnnouncement("Response ready.");
      queryClient.invalidateQueries({ queryKey: ["chat", "conversations"] });
      if (!conversationId) {
        skipNextConversationLoad.current = response.conversation_id;
        router.replace(`/workspace/${response.conversation_id}`);
      }
    } catch (error: unknown) {
      flushStreamDelta(assistantMessageId);
      if (abort.signal.aborted) {
        if (shownText) {
          // The server saves the partial answer as stopped.
          setAssistantMessage(assistantMessageId, { state: "stopped" });
          // Only the list: refetching this conversation could race the server's save
          // and replace the messages on screen with ones missing this turn.
          queryClient.invalidateQueries({ queryKey: ["chat", "conversations"], exact: true });
          if (newConversationId) {
            skipNextConversationLoad.current = newConversationId;
            router.replace(`/workspace/${newConversationId}`);
          }
        } else {
          // Nothing was saved: take the question back into the input.
          setMessages((current) =>
            current.filter(
              (message) => message.id !== assistantMessageId && message.id !== userMessage.id,
            ),
          );
          setQuery((currentQuery) => currentQuery || question);
        }
        setAnnouncement("Response stopped.");
        return;
      }
      setAssistantMessage(assistantMessageId, {
        state: "failed",
        question,
        error:
          error instanceof Error && error.message
            ? error.message
            : "We could not finish this answer. Please try again.",
      });
      setAnnouncement("");
    } finally {
      discardStreamDelta();
      if (streamAbort.current === abort) streamAbort.current = null;
      setIsPending(false);
      setStreamingMessageId(undefined);
      setStreamStatus("");
    }
  }

  function handleJumpToLatest() {
    const conversation = conversationRef.current;
    if (!conversation) return;

    shouldAutoScroll.current = true;
    conversation.scrollTo({
      top: conversation.scrollHeight,
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
    });
  }

  return (
    <section className="relative h-full min-h-0 w-full px-4 sm:px-6">
      {/* Announce progress only; streamed text would be read aloud chunk by chunk. */}
      <p aria-live="polite" className="sr-only" role="status">
        {announcement}
      </p>
      <div
        ref={conversationRef}
        className="absolute inset-0 overflow-y-auto"
        onScroll={(event) => {
          const conversation = event.currentTarget;
          shouldAutoScroll.current =
            conversation.scrollHeight - conversation.scrollTop - conversation.clientHeight < 80;
          setShowJumpToLatest(!shouldAutoScroll.current);
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
              {getApiErrorMessage(conversationQuery.error, "We could not load this conversation.")}
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
              <div className="mt-6 flex max-w-xl flex-wrap justify-center gap-2">
                {EXAMPLE_QUESTIONS.map((example) => (
                  <Button
                    className="h-auto rounded-full px-3 py-1.5 text-xs font-normal text-copy"
                    key={example}
                    size="sm"
                    type="button"
                    variant="outline"
                    onClick={() => void askQuestion(example)}
                  >
                    {example}
                  </Button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((message) => (
              <ChatMessageBubble
                key={message.id}
                message={message}
                streamingStatus={message.id === streamingMessageId ? streamStatus : undefined}
                onRetry={
                  message.question && !isPending
                    ? () => handleRetry(message.id, message.question as string)
                    : undefined
                }
              />
            ))
          )}
        </div>
      </div>

      <form
        className="absolute inset-x-0 bottom-0 z-20 bg-background px-4 pb-4 pt-3 sm:px-0"
        onSubmit={handleSubmit}
      >
        {showJumpToLatest && (
          <div className="pointer-events-none absolute inset-x-0 bottom-full flex justify-center pb-2">
            <Button
              aria-label="Jump to latest response"
              className="pointer-events-auto rounded-full border-border bg-background px-3 text-foreground shadow-[0_8px_30px_rgb(24_26_25/12%)] hover:bg-secondary"
              size="sm"
              type="button"
              variant="outline"
              onClick={handleJumpToLatest}
            >
              <ArrowDown aria-hidden="true" />
              Jump to latest
            </Button>
          </div>
        )}
        <div className="mx-auto max-w-3xl">
          <label className="sr-only" htmlFor="chat-question">
            Your question
          </label>
          <div className="flex items-end gap-2 rounded-2xl border border-border bg-background/70 p-2 shadow-[0_8px_30px_rgb(24_26_25/8%)] transition-shadow focus-within:border-primary/60 focus-within:shadow-[0_8px_30px_rgb(24_26_25/12%)]">
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
                <div className="inline-flex items-center gap-2 text-xs font-medium text-copy">
                  <Tooltip>
                    <TooltipTrigger
                      aria-label={webSearchEnabled ? "Disable web search" : "Enable web search"}
                      aria-pressed={webSearchEnabled}
                      className="rounded-md p-1 text-muted transition-colors hover:bg-secondary hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 aria-pressed:bg-primary/10 aria-pressed:text-primary aria-pressed:ring-1 aria-pressed:ring-primary/30"
                      type="button"
                      onClick={() => {
                        const enabled = !webSearchEnabled;
                        setWebSearchEnabled(enabled);
                        window.localStorage.setItem(WEB_SEARCH_STORAGE_KEY, String(enabled));
                      }}
                    >
                      <Globe2 aria-hidden="true" size={14} />
                    </TooltipTrigger>
                    <TooltipContent>
                      {webSearchEnabled
                        ? "Peka may search the public web when current information is needed."
                        : "Click to allow Peka to search the public web when needed."}
                    </TooltipContent>
                  </Tooltip>
                  <span>Web search</span>
                </div>
              </div>
            </div>
            {isPending ? (
              <Button
                aria-label="Stop response"
                className="rounded-full"
                key="stop"
                size="icon-lg"
                type="button"
                onClick={(event) => {
                  // Stopping re-renders this as the submit button before the click finishes;
                  // without this the same click would submit the restored question again.
                  event.preventDefault();
                  streamAbort.current?.abort();
                }}
              >
                <Square aria-hidden="true" className="fill-current" />
              </Button>
            ) : (
              <Button
                aria-label="Send message"
                className="rounded-full"
                key="send"
                size="icon-lg"
                type="submit"
              >
                <ArrowUp aria-hidden="true" />
              </Button>
            )}
          </div>
          <p id="chat-question-help" className="sr-only">
            Press Enter to send or Shift + Enter for a new line.
          </p>
          {validationError && (
            <p className="mt-2 text-sm text-danger" role="alert">
              {validationError}
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
  onRetry,
}: {
  message: DisplayMessage;
  streamingStatus?: string;
  onRetry?: () => void;
}) {
  const isUser = message.role === "user";
  const result = message.result;
  const [copied, setCopied] = useState(false);

  async function copyAnswer() {
    try {
      await navigator.clipboard.writeText(message.text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard access denied; the text stays selectable.
    }
  }

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
        {!isUser && streamingStatus && (
          <p className="mt-2 flex items-center gap-2 text-sm text-muted">
            <LoaderCircle aria-hidden="true" className="animate-spin" size={14} />
            {streamingStatus}
          </p>
        )}
        {message.state === "stopped" && (
          <p className="mt-2 text-xs font-medium text-muted">Response stopped</p>
        )}
        {message.state === "failed" && (
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <p className="text-sm text-danger" role="alert">
              {message.error}
            </p>
            {onRetry && (
              <Button size="sm" type="button" variant="outline" onClick={onRetry}>
                <RotateCcw aria-hidden="true" />
                Retry
              </Button>
            )}
          </div>
        )}
        {!isUser && message.text && !streamingStatus && (
          <Button
            aria-label={copied ? "Copied" : "Copy response"}
            className="mt-2 text-muted hover:text-foreground"
            size="icon-sm"
            type="button"
            variant="ghost"
            onClick={() => void copyAnswer()}
          >
            {copied ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}
          </Button>
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
  message: Pick<ChatMessage, "id" | "role" | "content" | "refused" | "citations" | "status">,
  conversationId?: string,
): DisplayMessage {
  return {
    id: message.id,
    role: message.role,
    text: message.content,
    ...(message.status === "stopped" ? { state: "stopped" as const } : {}),
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
