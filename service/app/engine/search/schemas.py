from pydantic import BaseModel, Field
from uuid import UUID


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)


class SearchResponse(BaseModel):
    file_id: UUID
    title: str
    heading: str
    snippet: str
    source_locations: list[dict]
    score: float
