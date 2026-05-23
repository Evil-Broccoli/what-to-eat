from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional at import time
    load_dotenv = None


ROOT_DIR = Path(__file__).resolve().parents[3]
if load_dotenv:
    load_dotenv(ROOT_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    app_name: str = "What To Eat API"
    api_prefix: str = "/api"
    data_path: Path = ROOT_DIR / "cook"
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    llm_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    llm_temperature: float = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
    llm_max_tokens: int = int(os.getenv("OPENAI_MAX_TOKENS", "2048"))
    top_k: int = 5
    max_context_chars: int = 6000

    neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user: str = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "what-to-eat")

    milvus_host: str = os.getenv("MILVUS_HOST", "localhost")
    milvus_port: str = os.getenv("MILVUS_PORT", "19530")
    milvus_collection: str = os.getenv("MILVUS_COLLECTION", "recipe_chunks")

    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    openai_base_url: str | None = os.getenv("OPENAI_BASE_URL") or None
    cors_origins: tuple[str, ...] = tuple(
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
        if origin.strip()
    )


settings = Settings()
