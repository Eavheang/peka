import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.auth.routes import authenticated
from app.chat.schemas import (
    ChatRequest, ChatResponse, Conversation, ConversationDetail,
    SourcePreviewRequest, SourcePreviewResponse,
)
from app.chat import service as chat_service
from app.chat.repository import ConversationNotFoundError
from app.chat.service import answer_from_knowledge

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)


@router.post("/source-preview", response_model=SourcePreviewResponse)
def source_preview(payload: SourcePreviewRequest, user: dict = Depends(authenticated)) -> dict:
    result = chat_service.preview_source(payload, user["role"])
    if result is None or not result["content"].strip():
        raise HTTPException(status_code=404, detail="Source preview unavailable")
    return result


@router.post("", response_model=ChatResponse, response_model_exclude_none=True)
def chat(payload: ChatRequest, user: dict = Depends(authenticated)) -> ChatResponse:
    try:
        history = []
        if payload.conversation_id is not None:
            conversation = chat_service.get_conversation(payload.conversation_id, user["id"])
            if conversation is None:
                raise ConversationNotFoundError
            history = conversation["messages"]
        if payload.web_search:
            answer = answer_from_knowledge(
                payload.query, user["role"], history, web_search=True,
            )
        else:
            answer = answer_from_knowledge(payload.query, user["role"], history)
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


@router.get("/conversations", response_model=list[Conversation])
def conversations(user: dict = Depends(authenticated)) -> list[dict]:
    return chat_service.list_conversations(user["id"])


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
