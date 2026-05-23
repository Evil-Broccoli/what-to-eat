from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.recipe import RecipeSummary


class ChatRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    stream: bool = False


class Source(BaseModel):
    recipe_id: str
    recipe_name: str
    category: str = "其他"
    difficulty: str = "未知"
    score: float = 0


class ChatResponse(BaseModel):
    answer: str
    strategy: str
    sources: list[Source] = Field(default_factory=list)


class IndexStatus(BaseModel):
    neo4j: bool
    milvus: bool
    recipe_count: int
    chunk_count: int
    last_build: str | None = None


class RebuildResponse(IndexStatus):
    message: str
    failed_sources: list[str] = Field(default_factory=list)
