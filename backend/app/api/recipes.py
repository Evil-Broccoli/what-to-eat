from fastapi import APIRouter, HTTPException, Query

from app.schemas.recipe import RecipeDetail, RecipeListResponse
from app.services.rag_service import rag_service

router = APIRouter(prefix="/recipes", tags=["recipes"])


@router.get("", response_model=RecipeListResponse)
def list_recipes(
    category: str | None = None,
    difficulty: str | None = None,
    q: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return rag_service.list_recipes(category=category, difficulty=difficulty, q=q, limit=limit, offset=offset)


@router.get("/{recipe_id}", response_model=RecipeDetail)
def get_recipe(recipe_id: str):
    recipe = rag_service.get_recipe(recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe
