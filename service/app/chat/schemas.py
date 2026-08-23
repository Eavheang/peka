import json

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    query: str = Field(min_length=1)


class Citation(BaseModel):
    title: str
    heading: str
    page: int | None = None
    source_locations: list[dict]


class ChatResponse(BaseModel):
    answer: str
    refused: bool
    citations: list[Citation]
