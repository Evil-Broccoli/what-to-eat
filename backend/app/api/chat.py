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
    def sse(event: str, payload: dict):
        return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

    def event_stream():
        try:
            records, sources, strategy = rag_service.retrieve(request.query)
            yield sse("meta", {"strategy": strategy, "sources": [item.model_dump() for item in sources]})
            for token in rag_service.stream_answer(request.query, records, strategy):
                yield sse("token", {"content": token})
            yield sse("done", {})
        except Exception as exc:
            yield sse("error", {"message": f"问答生成失败：{exc}"})
            yield sse("done", {})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
