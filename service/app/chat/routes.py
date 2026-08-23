from fastapi import APIRouter, Depends, HTTPException

from app.auth.routes import authenticated
from app.chat.schemas import ChatRequest, ChatResponse
from app.chat.service import answer_from_knowledge

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(payload: ChatRequest, user: dict = Depends(authenticated)) -> ChatResponse:
    if not payload.query.strip():
        raise HTTPException(status_code=422, detail="Query must not be empty")
    try:
        return answer_from_knowledge(payload.query, user["role"])
    except (RuntimeError,) as error:
        raise HTTPException(status_code=503, detail=str(error)) from None
