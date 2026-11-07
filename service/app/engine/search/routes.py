from fastapi import APIRouter, Depends, HTTPException

from app.auth.routes import authenticated
from app.config import settings
from app.engine.search.schemas import SearchRequest, SearchResponse
from app.engine.search.service import search_knowledge

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=list[SearchResponse])
def search(payload: SearchRequest, user: dict = Depends(authenticated)) -> list[dict]:
    if not payload.query.strip():
        raise HTTPException(status_code=422, detail="Query must not be empty")
    try:
        return search_knowledge(payload.query, user["role"], top_k=settings.search_top_k)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from None
