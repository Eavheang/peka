from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    conversation_id: UUID | None = None
    # Client-chosen id for a new conversation, so the client knows it even when the
    # stream is stopped before the server could send it back.
    new_conversation_id: UUID | None = None
    web_search: bool = False
    timezone: str | None = Field(default=None, max_length=64)

    @field_validator("query", mode="before")
    @classmethod
    def trim_query(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class Citation(BaseModel):
    title: str
    heading: str
    page: int | None = None
    source_locations: list[dict]
    chunk_id: UUID | None = None
    file_id: UUID | None = None
    url: str | None = None
    excerpt: str | None = None


class SourcePreviewRequest(BaseModel):
    chunk_id: UUID | None = None
    title: str = Field(min_length=1, max_length=1024)
    heading: str = Field(max_length=4096)


class SourcePreviewResponse(BaseModel):
    content: str
    file_id: UUID | None = None


class ChatMessage(BaseModel):
    id: UUID
    role: str
    content: str
    refused: bool
    citations: list[Citation]
    status: str
    created_at: datetime


class Conversation(BaseModel):
    id: UUID
    owner_id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationDetail(Conversation):
    messages: list[ChatMessage]


class ConversationPage(BaseModel):
    items: list[Conversation]
    next_cursor: str | None = None


class ChatResponse(BaseModel):
    answer: str
    refused: bool
    citations: list[Citation]
    conversation_id: UUID | None = None
    messages: list[ChatMessage] | None = None
