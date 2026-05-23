from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.rag_service import rag_service

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest):
    return rag_service.chat(request.query)


@router.post("/stream")
def stream_chat(request: ChatRequest):
    def event_stream():
        response = rag_service.chat(request.query)
        yield f"event: meta\ndata: {json.dumps({'strategy': response.strategy, 'sources': [item.model_dump() for item in response.sources]}, ensure_ascii=False)}\n\n"
        for char in response.answer:
            yield f"event: token\ndata: {json.dumps({'content': char}, ensure_ascii=False)}\n\n"
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
