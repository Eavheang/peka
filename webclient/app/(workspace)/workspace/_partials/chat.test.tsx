import { expect, test } from "bun:test";
import { renderToStaticMarkup } from "react-dom/server";

import type { ChatMessage, Citation } from "@/interface/chat";
import { sendChatMessageStream } from "@/services/chat";
import { applyStreamResult, ChatMessageBubble, toDisplayMessage } from "./chat";

const REFUSAL = "I could not find enough evidence in your documents to answer that.";
const ANSWER = "Every employee gets 20 days of leave.";

const citation: Citation = {
  title: "policy.pdf",
  heading: "Leave",
  page: 3,
  source_locations: [],
};

function sse(events: unknown[]): string {
  return `${events.map((event) => `data: ${JSON.stringify(event)}\n`).join("\n")}data: [DONE]\n`;
}

function doneResponse(overrides: Record<string, unknown>) {
  return {
    answer: ANSWER,
    refused: false,
    citations: [citation],
    conversation_id: "conv-1",
    messages: [],
    ...overrides,
  };
}

async function readStream(events: unknown[]) {
  const previousFetch = globalThis.fetch;
  let text = "";
  globalThis.fetch = async () =>
    new Response(sse(events), {
      status: 200,
      headers: { "Content-Type": "text/event-stream" },
    });
  try {
    const response = await sendChatMessageStream(
      { query: "What is the leave policy?" },
      (update) => {
        if (update.type === "text") text += update.delta;
      },
    );
    return { response, text };
  } finally {
    globalThis.fetch = previousFetch;
  }
}

function renderMessage(
  message: Parameters<typeof ChatMessageBubble>[0]["message"],
  streamingStatus?: string,
) {
  return renderToStaticMarkup(
    <ChatMessageBubble message={message} streamingStatus={streamingStatus} />,
  );
}

test("a refused stream renders the refusal card and hides citations", async () => {
  const { response, text } = await readStream([
    { type: "status", message: "Searching your documents..." },
    { type: "text", delta: REFUSAL },
    {
      type: "done",
      response: doneResponse({
        answer: REFUSAL,
        refused: true,
        answer_status: "refused",
        citations: [citation],
      }),
    },
  ]);

  expect(response.answer_status).toBe("refused");
  expect(response.answer).toBe(REFUSAL);
  expect(response.citations[0]?.title).toBe("policy.pdf");
  expect(text).toBe(REFUSAL);

  const html = renderMessage(
    applyStreamResult({ id: "assistant-1", role: "assistant", text }, response),
  );

  expect(html).toContain('role="status"');
  expect(html).toContain("No evidence found");
  expect(html).toContain(REFUSAL);
  expect(html).toContain("Upload a relevant document or rephrase the question.");
  expect(html.includes("Sources")).toBe(false);
  expect(html.includes('role="alert"')).toBe(false);
  expect(html.includes("Not enough evidence")).toBe(false);
});

test("a stream with no answer_status renders a normal answer and its sources", async () => {
  const { response, text } = await readStream([
    { type: "text", delta: ANSWER },
    { type: "done", response: doneResponse({}) },
  ]);

  expect(response.answer_status).toBe("answered");
  expect(response.refused).toBe(false);

  const html = renderMessage(
    applyStreamResult({ id: "assistant-2", role: "assistant", text }, response),
  );

  expect(html).toContain(ANSWER);
  expect(html).toContain("Sources (1)");
  expect(html.includes("No evidence found")).toBe(false);
  expect(html.includes('role="status"')).toBe(false);
});

test("an unknown answer_status renders a normal answer", async () => {
  const { response } = await readStream([
    { type: "text", delta: ANSWER },
    { type: "done", response: doneResponse({ answer_status: "nope" }) },
  ]);

  expect(response.answer_status).toBe("answered");

  const html = renderMessage(
    applyStreamResult({ id: "assistant-3", role: "assistant", text: response.answer }, response),
  );

  expect(html).toContain("Sources (1)");
  expect(html.includes("No evidence found")).toBe(false);
});

test("an answered stream keeps the normal answer and its sources", async () => {
  const { response, text } = await readStream([
    { type: "text", delta: ANSWER },
    { type: "done", response: doneResponse({ answer_status: "answered" }) },
  ]);

  expect(response.answer_status).toBe("answered");

  const html = renderMessage(
    applyStreamResult({ id: "assistant-4", role: "assistant", text }, response),
  );

  expect(html).toContain(ANSWER);
  expect(html).toContain("Sources (1)");
  expect(html.includes("No evidence found")).toBe(false);
});

test("a reloaded refused message renders the same card", () => {
  const message: ChatMessage = {
    id: "msg-refused",
    role: "assistant",
    content: REFUSAL,
    refused: true,
    citations: [citation],
    status: "completed",
    created_at: "2026-10-06T00:00:00.000Z",
  };

  const html = renderMessage(toDisplayMessage(message, "conv-1"));

  expect(html).toContain('role="status"');
  expect(html).toContain("No evidence found");
  expect(html).toContain(REFUSAL);
  expect(html).toContain("Upload a relevant document or rephrase the question.");
  expect(html.includes("Sources")).toBe(false);
});

test("a reloaded answered message keeps its sources", () => {
  const message: ChatMessage = {
    id: "msg-answered",
    role: "assistant",
    content: ANSWER,
    refused: false,
    citations: [citation],
    status: "completed",
    created_at: "2026-10-06T00:00:00.000Z",
  };

  const html = renderMessage(toDisplayMessage(message, "conv-1"));

  expect(html).toContain(ANSWER);
  expect(html).toContain("Sources (1)");
  expect(html.includes("No evidence found")).toBe(false);
});

test("a stream error still rejects with the server message", async () => {
  let caught: unknown;
  try {
    await readStream([{ type: "error", message: "The model is unavailable." }]);
  } catch (error) {
    caught = error;
  }

  expect(caught instanceof Error ? caught.message : caught).toBe("The model is unavailable.");
});

test("a loading answer shows its status and not the refusal card", () => {
  const html = renderMessage(
    { id: "pending", role: "assistant", text: "" },
    "Searching your documents...",
  );

  expect(html).toContain("Searching your documents...");
  expect(html.includes("No evidence found")).toBe(false);
  expect(html.includes('role="alert"')).toBe(false);
});
