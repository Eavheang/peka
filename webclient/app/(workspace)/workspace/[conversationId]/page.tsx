import { ChatPanel } from "../_partials/chat";

export default async function ConversationPage({
  params,
}: {
  params: Promise<{ conversationId: string }>;
}) {
  const { conversationId } = await params;

  return <ChatPanel conversationId={conversationId} />;
}
