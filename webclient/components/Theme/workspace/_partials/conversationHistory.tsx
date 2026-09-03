"use client";

import Link from "next/link";
import { LoaderCircle, MessageSquare } from "lucide-react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { Conversation } from "@/interface/chat";

export function ConversationHistory({
  collapsed = false,
  conversations,
  error,
  loading,
  onNavigate,
  pathname,
}: {
  collapsed?: boolean;
  conversations?: Conversation[];
  error: boolean;
  loading: boolean;
  onNavigate?: () => void;
  pathname: string;
}) {
  if (collapsed) {
    return (
      <div className="mt-5 border-t border-white/10 pt-5">
        {conversations?.map((conversation) => (
          <ConversationLink
            key={conversation.id}
            collapsed
            conversation={conversation}
            onNavigate={onNavigate}
            pathname={pathname}
          />
        ))}
      </div>
    );
  }

  return (
    <section className="mt-6 border-t border-white/10 pt-5" aria-label="Recent chats">
      <p className="px-3 pb-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-white/45">
        Recent chats
      </p>
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
            onNavigate={onNavigate}
            pathname={pathname}
          />
        ))}
      </div>
    </section>
  );
}

function ConversationLink({
  collapsed = false,
  conversation,
  onNavigate,
  pathname,
}: {
  collapsed?: boolean;
  conversation: Conversation;
  onNavigate?: () => void;
  pathname: string;
}) {
  const isActive = pathname === `/workspace/${conversation.id}`;
  const title = conversation.title || "Untitled chat";
  const link = (
    <Link
      aria-label={collapsed ? title : undefined}
      className={`flex min-w-0 items-center gap-3 rounded-md px-3 py-2.5 text-sm transition-colors hover:bg-white/10 hover:text-white ${isActive ? "bg-white/10 text-white" : "text-white/65"} ${collapsed ? "justify-center" : ""}`}
      href={`/workspace/${conversation.id}`}
      title={collapsed ? title : undefined}
      onClick={onNavigate}
    >
      <MessageSquare aria-hidden="true" size={17} strokeWidth={1.8} />
      {!collapsed && <span className="truncate">{title}</span>}
    </Link>
  );

  return collapsed ? (
    <Tooltip>
      <TooltipTrigger render={link} />
      <TooltipContent side="right">{title}</TooltipContent>
    </Tooltip>
  ) : (
    link
  );
}
