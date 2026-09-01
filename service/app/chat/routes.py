from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.auth.routes import authenticated
from app.chat.schemas import ChatRequest, ChatResponse, Conversation, ConversationDetail
from app.chat import service as chat_service
from app.chat.repository import ConversationNotFoundError
from app.chat.service import answer_from_knowledge

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse, response_model_exclude_none=True)
def chat(payload: ChatRequest, user: dict = Depends(authenticated)) -> ChatResponse:
    try:
        answer = answer_from_knowledge(payload.query, user["role"])
        return chat_service.persist_response(
            payload.query,
            user["id"],
            answer,
            payload.conversation_id,
        )
    except ConversationNotFoundError:
        raise HTTPException(status_code=404, detail="Conversation not found") from None
    except (RuntimeError,) as error:
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
