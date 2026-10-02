import asyncio
import json
import logging
from uuid import UUID

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


@router.post("", response_model=ChatResponse, response_model_exclude_none=True)
def chat(payload: ChatRequest, user: dict = Depends(authenticated)) -> ChatResponse:
    try:
        history = _conversation_history(payload, user["id"])
        if payload.web_search:
            answer = answer_from_knowledge(
                payload.query, user["role"], history, web_search=True,
                conversation_id=payload.conversation_id, actor_id=user["id"],
            )
        else:
            answer = answer_from_knowledge(
                payload.query, user["role"], history,
                conversation_id=payload.conversation_id, actor_id=user["id"],
            )
        return chat_service.persist_response(
            payload.query,
            user["id"],
            answer,
            payload.conversation_id,
        )
    except ConversationNotFoundError:
        raise HTTPException(status_code=404, detail="Conversation not found") from None
    except (RuntimeError,) as error:
        logger.warning("Chat request failed: %s", error)
        raise HTTPException(status_code=503, detail=str(error)) from None


@router.post("/stream")
async def chat_stream(payload: ChatRequest, user: dict = Depends(authenticated)) -> StreamingResponse:
    try:
        history = _conversation_history(payload, user["id"])
    except ConversationNotFoundError:
        raise HTTPException(status_code=404, detail="Conversation not found") from None

    async def events():
        try:
            async for event in chat_service.stream_answer_from_knowledge(
                payload.query,
                user["role"],
                history,
                web_search=payload.web_search,
                conversation_id=payload.conversation_id,
                actor_id=user["id"],
            ):
                if isinstance(event, chat_service.ChatStreamStatus):
                    yield _sse({"type": "status", "message": event.message})
                elif isinstance(event, chat_service.ChatStreamText):
                    yield _sse({"type": "text", "delta": event.delta})
                else:
                    response = await asyncio.to_thread(
                        chat_service.persist_response,
                        payload.query,
                        user["id"],
                        event.response,
                        payload.conversation_id,
                    )
                    yield _sse({
                        "type": "done",
                        "response": response.model_dump(mode="json", exclude_none=True),
                    })
                    yield "data: [DONE]\n\n"
        except RuntimeError as error:
            logger.warning("Streaming chat request failed: %s", error)
            yield _sse({"type": "error", "message": str(error)})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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
