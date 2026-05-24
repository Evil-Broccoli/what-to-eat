from __future__ import annotations

import logging
import socket
from typing import Any

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - optional dependency
    OpenAI = None

try:
    from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections, utility
except ImportError:  # pragma: no cover - optional dependency
    Collection = CollectionSchema = DataType = FieldSchema = connections = utility = None

logger = logging.getLogger(__name__)


class MilvusIndexConstructionModule:
    """Builds and searches a Milvus vector index using an embedding API."""

    def __init__(
        self,
        host: str,
        port: str,
        collection_name: str,
        model_name: str,
        dimension: int,
        api_key: str | None,
        base_url: str | None = None,
        batch_size: int = 64,
    ):
        self.host = host
        self.port = port
        self.collection_name = collection_name
        self.model_name = model_name
        self.dimension = dimension
        self.api_key = api_key
        self.base_url = base_url
        self.batch_size = batch_size
        self._client = None
        self._collection = None

    @property
    def is_available(self) -> bool:
        if Collection is None or not self._can_embed() or not self._can_connect_port():
            return False
        try:
            collection = self.collection
            return self._collection_matches_dimension(collection)
        except Exception:
            return False

    @property
    def client(self):
        if OpenAI is None:
            raise RuntimeError("openai package is not installed")
        if not self.api_key:
            raise RuntimeError("Embedding API key is not configured")
        if self._client is None:
            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        return self._client

    @property
    def collection(self):
        if Collection is None:
            raise RuntimeError("pymilvus package is not installed")
        connections.connect(alias="default", host=self.host, port=self.port)
        if not utility.has_collection(self.collection_name):
            self._create_collection()
        if self._collection is None:
            self._collection = Collection(self.collection_name)
            self._collection.load()
        return self._collection

    def rebuild(self, chunks: list[dict[str, Any]]) -> int:
        if Collection is None or not self._can_embed() or not self._can_connect_port():
            return 0
        connections.connect(alias="default", host=self.host, port=self.port)
        if utility.has_collection(self.collection_name):
            utility.drop_collection(self.collection_name)
            self._collection = None
        collection = self.collection
        if not chunks:
            return 0

        vectors = self.embed([chunk["text"] for chunk in chunks])
        collection.insert(
            [
                [chunk["id"] for chunk in chunks],
                [chunk["recipe_id"] for chunk in chunks],
                [chunk["chunk_id"] for chunk in chunks],
                [chunk["chunk_type"] for chunk in chunks],
                [chunk["recipe_name"] for chunk in chunks],
                [chunk["category"] for chunk in chunks],
                [chunk["difficulty"] for chunk in chunks],
                [chunk["text"][:8000] for chunk in chunks],
                [str(chunk["metadata"]) for chunk in chunks],
                vectors,
            ]
        )
        collection.flush()
        collection.load()
        return len(chunks)

    def search(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        if not self.is_available:
            return []
        try:
            vector = self.embed([query])[0]
            results = self.collection.search(
                data=[vector],
                anns_field="embedding",
                param={"metric_type": "COSINE", "params": {"ef": 64}},
                limit=limit,
                output_fields=["recipe_id", "recipe_name", "category", "difficulty", "text"],
            )
        except Exception as exc:
            logger.warning("Milvus vector search failed, using fallback retrieval: %s", exc)
            return []

        hits: list[dict[str, Any]] = []
        for hit in results[0]:
            entity = hit.entity
            hits.append(
                {
                    "recipe_id": entity.get("recipe_id"),
                    "recipe_name": entity.get("recipe_name"),
                    "category": entity.get("category"),
                    "difficulty": entity.get("difficulty"),
                    "text": entity.get("text"),
                    "score": float(hit.score),
                }
            )
        return hits

    def count(self) -> int:
        if not self.is_available:
            return 0
        return self.collection.num_entities

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            vectors.extend(self._embed_batch(batch))
        return vectors

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        payload: dict[str, Any] = {"input": texts, "model": self.model_name}
        if self.dimension:
            payload["dimensions"] = self.dimension

        try:
            response = self.client.embeddings.create(**payload)
        except Exception as exc:
            if "dimension" not in str(exc).lower():
                raise
            payload.pop("dimensions", None)
            response = self.client.embeddings.create(**payload)

        vectors = [item.embedding for item in response.data]
        for vector in vectors:
            if len(vector) != self.dimension:
                raise ValueError(
                    f"Embedding dimension mismatch: expected {self.dimension}, got {len(vector)}. "
                    "Update EMBEDDING_DIMENSION or choose a matching embedding model."
                )
        return vectors

    def _create_collection(self) -> None:
        schema = CollectionSchema(
            fields=[
                FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=128, is_primary=True),
                FieldSchema(name="recipe_id", dtype=DataType.VARCHAR, max_length=64),
                FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=64),
                FieldSchema(name="chunk_type", dtype=DataType.VARCHAR, max_length=64),
                FieldSchema(name="recipe_name", dtype=DataType.VARCHAR, max_length=256),
                FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=64),
                FieldSchema(name="difficulty", dtype=DataType.VARCHAR, max_length=64),
                FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=8192),
                FieldSchema(name="metadata", dtype=DataType.VARCHAR, max_length=2048),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dimension),
            ],
            description="Recipe chunks for What To Eat RAG",
        )
        self._collection = Collection(self.collection_name, schema)
        self._collection.create_index(
            "embedding",
            {"index_type": "HNSW", "metric_type": "COSINE", "params": {"M": 16, "efConstruction": 128}},
        )

    def _collection_matches_dimension(self, collection) -> bool:
        for field in collection.schema.fields:
            if field.name == "embedding":
                return int(field.params.get("dim", 0)) == self.dimension
        return False

    def _can_embed(self) -> bool:
        return OpenAI is not None and bool(self.api_key)

    def _can_connect_port(self) -> bool:
        try:
            with socket.create_connection((self.host, int(self.port)), timeout=0.5):
                return True
        except OSError:
            return False
