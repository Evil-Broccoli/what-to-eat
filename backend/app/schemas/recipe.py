from __future__ import annotations

from pydantic import BaseModel, Field


class Ingredient(BaseModel):
    name: str
    amount: str | None = None
    required: bool = True


class RecipeSummary(BaseModel):
    id: str
    name: str
    category: str = "其他"
    difficulty: str = "未知"
    source: str
    description: str = ""


class RecipeDetail(RecipeSummary):
    ingredients: list[Ingredient] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    sections: dict[str, str] = Field(default_factory=dict)
    related: list[RecipeSummary] = Field(default_factory=list)


class RecipeListResponse(BaseModel):
    items: list[RecipeSummary]
    total: int
