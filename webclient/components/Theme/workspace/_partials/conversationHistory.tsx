"use client";

import Link from "next/link";
import { LoaderCircle, MessageSquare, Trash2 } from "lucide-react";

import type { Conversation } from "@/interface/chat";

export function ConversationHistory({
  conversations,
  error,
  loading,
  onDelete,
  onNavigate,
  pathname,
}: {
  conversations?: Conversation[];
  error: boolean;
  loading: boolean;
  onDelete: (conversation: Conversation) => void;
  onNavigate?: () => void;
  pathname: string;
}) {
  return (
    <section
      className="mt-6 flex min-h-0 flex-1 flex-col border-t border-white/10 pt-5"
      aria-label="Recent chats"
    >
      <p className="px-3 pb-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-white/45">
        Recent chats
      </p>
      <div className="workspace-scrollbar min-h-0 flex-1 overflow-y-auto">
        {loading && (
          <p className="flex items-center gap-2 px-3 py-2 text-xs text-white/45">
            <LoaderCircle aria-hidden="true" className="animate-spin" size={13} />
            Loading chats...
          </p>
        )}
        {error && <p className="px-3 py-2 text-xs text-white/45">Could not load chats.</p>}
        {!loading && !error && conversations?.length === 0 && (
          <p className="px-3 py-2 text-xs leading-5 text-white/45">
            Your saved chats will appear here.
          </p>
        )}
        <div className="grid gap-1">
          {conversations?.map((conversation) => (
            <ConversationLink
              key={conversation.id}
              conversation={conversation}
              onDelete={onDelete}
              onNavigate={onNavigate}
              pathname={pathname}
            />
          ))}
        </div>
      </div>
    </section>
  );
}

function ConversationLink({
  conversation,
  onDelete,
  onNavigate,
  pathname,
}: {
  conversation: Conversation;
  onDelete: (conversation: Conversation) => void;
  onNavigate?: () => void;
  pathname: string;
}) {
  const isActive = pathname === `/workspace/${conversation.id}`;
  const title = conversation.title || "Untitled chat";
  const link = (
    <Link
      className={`flex min-w-0 flex-1 items-center gap-3 rounded-md px-3 py-2.5 text-sm transition-colors hover:bg-white/10 hover:text-white ${isActive ? "bg-white/10 text-white" : "text-white/65"}`}
      href={`/workspace/${conversation.id}`}
      onClick={onNavigate}
    >
      <MessageSquare aria-hidden="true" className="shrink-0" size={17} strokeWidth={1.8} />
      <span className="min-w-0 flex-1 truncate">{title}</span>
    </Link>
  );

  const deleteButton = (
    <button
      aria-label={`Delete ${title}`}
      className="shrink-0 rounded-md p-2 text-white/45 transition-colors hover:bg-danger/20 hover:text-danger focus-visible:text-white"
      title={`Delete ${title}`}
      type="button"
      onClick={(event) => {
        event.preventDefault();
        event.stopPropagation();
        onDelete(conversation);
        onNavigate?.();
      }}
    >
      <Trash2 aria-hidden="true" size={15} strokeWidth={1.8} />
    </button>
  );

  const content = (
    <div className="group flex min-w-0 items-center gap-1">
      {link}
      {deleteButton}
    </div>
  );

  return content;
}
