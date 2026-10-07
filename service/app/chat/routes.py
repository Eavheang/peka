import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from contextlib import aclosing
from uuid import UUID

import anyio

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse

from app.auth.routes import authenticated
from app.chat.schemas import (
    ChatRequest, ChatResponse, ConversationDetail, ConversationPage,
    SourcePreviewRequest, SourcePreviewResponse,
)
from app.chat import service as chat_service
from app.chat.repository import ConversationNotFoundError
from app.chat.service import answer_from_knowledge

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)


@router.post("/source-preview", response_model=SourcePreviewResponse, response_model_exclude_none=True)
def source_preview(payload: SourcePreviewRequest, user: dict = Depends(authenticated)) -> dict:
    result = chat_service.preview_source(payload, user["role"])
    if result is None or not result["content"].strip():
        raise HTTPException(status_code=404, detail="Source preview unavailable")
    return result


def _conversation_history(payload: ChatRequest, user_id: UUID) -> list[dict]:
    if payload.conversation_id is None:
        return []
    conversation = chat_service.get_conversation(payload.conversation_id, user_id)
    if conversation is None:
        raise ConversationNotFoundError
    return conversation["messages"]


def _prepare(payload: ChatRequest, user_id: UUID) -> tuple[ChatRequest, list[dict]]:
    history = _conversation_history(payload, user_id)
    if not payload.regenerate:
        return payload, history
    if len(history) < 2 or history[-1]["role"] != "assistant" or history[-2]["role"] != "user":
        raise HTTPException(status_code=409, detail="There is no answer to regenerate")
    return payload.model_copy(update={"query": history[-2]["content"]}), history[:-2]


@router.post("", response_model=ChatResponse, response_model_exclude_none=True)
def chat(payload: ChatRequest, user: dict = Depends(authenticated)) -> ChatResponse:
    try:
        payload, history = _prepare(payload, user["id"])
        answer = answer_from_knowledge(
            payload.query,
            user["role"],
            history,
            web_search=payload.web_search,
            timezone=payload.timezone,
        )
        return chat_service.persist_response(
            payload.query,
            user["id"],
            answer,
            payload.conversation_id,
            replace_last=payload.regenerate,
        )
    except ConversationNotFoundError:
        raise HTTPException(status_code=404, detail="Conversation not found") from None
    except (RuntimeError,) as error:
        logger.warning("Chat request failed: %s", error)
        raise HTTPException(status_code=503, detail=str(error)) from None


@router.post("/stream")
async def chat_stream(payload: ChatRequest, user: dict = Depends(authenticated)) -> StreamingResponse:
    try:
        payload, history = _prepare(payload, user["id"])
    except ConversationNotFoundError:
        raise HTTPException(status_code=404, detail="Conversation not found") from None

    return StreamingResponse(
        _stream_events(payload, user, history),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _stream_events(payload: ChatRequest, user: dict, history: list[dict]) -> AsyncIterator[str]:
    started = time.monotonic()
    metrics: dict = {"model": None, "ttft_ms": None}
    shown: list[str] = []  # the text the client currently displays
    finished = False
    try:
        metrics["model"] = await asyncio.to_thread(chat_service.model_name)
        async with aclosing(chat_service.stream_answer_from_knowledge(
            payload.query,
            user["role"],
            history,
            web_search=payload.web_search,
            timezone=payload.timezone,
        )) as events:
            async for event in events:
                if isinstance(event, chat_service.ChatStreamStatus):
                    yield _sse({"type": "status", "message": event.message})
                elif isinstance(event, chat_service.ChatStreamReset):
                    shown.clear()
                    yield _sse({"type": "reset"})
                elif isinstance(event, chat_service.ChatStreamText):
                    if metrics["ttft_ms"] is None:
                        metrics["ttft_ms"] = round((time.monotonic() - started) * 1000)
                    shown.append(event.delta)
                    yield _sse({"type": "text", "delta": event.delta})
                else:
                    finished = True
                    try:
                        # persist_response writes the chat audit row. Keep that insert
                        # off the event loop so a slow database does not stall the stream.
                        response = await asyncio.to_thread(
                            chat_service.persist_response,
                            payload.query,
                            user["id"],
                            event.response,
                            payload.conversation_id,
                            metrics=metrics,
                            new_conversation_id=payload.new_conversation_id,
                            replace_last=payload.regenerate,
                        )
                    except Exception:
                        logger.exception("Saving the chat answer failed")
                        await asyncio.to_thread(
                            chat_service.audit_unsaved_turn, "chat_turn_failed", user["id"],
                            payload.conversation_id, {**metrics, "reason": "save_failed"},
                        )
                        yield _sse({"type": "error", "message": "We could not save this answer. Please try again."})
                        return
                    yield _sse({
                        "type": "done",
                        "response": response.model_dump(mode="json", exclude_none=True),
                    })
                    yield "data: [DONE]\n\n"
    except (asyncio.CancelledError, GeneratorExit):
        # The client disconnected (Stop, closed tab). Closing the answer stream above
        # cancels the model request; a search or retry already in a worker thread
        # finishes on its own and its result is dropped.
        if not finished:
            with anyio.CancelScope(shield=True):
                await asyncio.to_thread(_save_stopped, payload, user["id"], "".join(shown).strip(), metrics)
        raise
    except Exception as error:
        logger.warning("Streaming chat request failed: %s", error, exc_info=not isinstance(error, RuntimeError))
        finished = True
        await asyncio.to_thread(
            chat_service.audit_unsaved_turn, "chat_turn_failed", user["id"],
            payload.conversation_id, {**metrics, "reason": type(error).__name__},
        )
        message = str(error) if isinstance(error, RuntimeError) else "The answer could not be generated."
        yield _sse({"type": "error", "message": message})


def _save_stopped(payload: ChatRequest, user_id: UUID, partial: str, metrics: dict) -> None:
    try:
        if partial:
            chat_service.persist_response(
                payload.query,
                user_id,
                ChatResponse(answer=partial, refused=False, citations=[]),
                payload.conversation_id,
                status="stopped",
                metrics=metrics,
                new_conversation_id=payload.new_conversation_id,
                replace_last=payload.regenerate,
            )
        else:
            chat_service.audit_unsaved_turn("chat_turn_stopped", user_id, payload.conversation_id, metrics)
    except Exception:
        logger.exception("Saving the stopped chat answer failed")


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.get("/conversations", response_model=ConversationPage)
def conversations(
    user: dict = Depends(authenticated),
    limit: int = Query(default=15, ge=1, le=50),
    cursor: str | None = Query(default=None),
) -> dict:
    try:
        return chat_service.list_conversations(user["id"], limit, cursor)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation cursor") from None


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def conversation(conversation_id: UUID, user: dict = Depends(authenticated)) -> dict:
    result = chat_service.get_conversation(conversation_id, user["id"])
    if result is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return result


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_conversation(conversation_id: UUID, user: dict = Depends(authenticated)) -> Response:
    if not chat_service.delete_conversation(conversation_id, user["id"]):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
