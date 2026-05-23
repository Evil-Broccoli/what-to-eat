from fastapi import APIRouter

from app.schemas.chat import IndexStatus, RebuildResponse
from app.services.rag_service import rag_service

router = APIRouter(prefix="/index", tags=["index"])


@router.get("/status", response_model=IndexStatus)
def status():
    return rag_service.health()


@router.post("/rebuild", response_model=RebuildResponse)
def rebuild():
    return rag_service.rebuild()
