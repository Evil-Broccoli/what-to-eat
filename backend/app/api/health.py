from fastapi import APIRouter

from app.schemas.chat import IndexStatus
from app.services.rag_service import rag_service

router = APIRouter(tags=["health"])


@router.get("/health", response_model=IndexStatus)
def health():
    return rag_service.health()
