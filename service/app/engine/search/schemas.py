from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)


class SearchResponse(BaseModel):
    title: str
    heading: str
    snippet: str
    source_locations: list[dict]
    score: float
