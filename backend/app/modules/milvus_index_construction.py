from __future__ import annotations

import logging
import socket
from typing import Any

try:
    from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections, utility
except ImportError:  # pragma: no cover - optional dependency
    Collection = CollectionSchema = DataType = FieldSchema = connections = utility = None

try:
    from sentence_transformers import SentenceTransformer
except ImportError:  # pragma: no cover - optional dependency
    SentenceTransformer = None

logger = logging.getLogger(__name__)


class MilvusIndexConstructionModule:
    """Builds and searches a Milvus vector index for recipe chunks."""

    def __init__(self, host: str, port: str, collection_name: str, model_name: str):
        self.host = host
        self.port = port
        self.collection_name = collection_name
        self.model_name = model_name
        self._model = None
        self._collection = None

    @property
    def is_available(self) -> bool:
        if Collection is None or SentenceTransformer is None:
            return False
        if not self._can_connect_port():
            return False
        try:
            self.collection
            return True
        except Exception:
            return False

    @property
    def model(self):
        if SentenceTransformer is None:
            raise RuntimeError("sentence-transformers package is not installed")
        if self._model is None:
            self._model = SentenceTransformer(self.model_name)
        return self._model

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
        if not self.is_available:
            return 0
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
        vector = self.embed([query])[0]
        results = self.collection.search(
            data=[vector],
            anns_field="embedding",
            param={"metric_type": "COSINE", "params": {"ef": 64}},
            limit=limit,
            output_fields=["recipe_id", "recipe_name", "category", "difficulty", "text"],
        )
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
        return self.model.encode(texts, normalize_embeddings=True).tolist()

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
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=512),
            ],
            description="Recipe chunks for What To Eat RAG",
        )
        self._collection = Collection(self.collection_name, schema)
        self._collection.create_index(
            "embedding",
            {"index_type": "HNSW", "metric_type": "COSINE", "params": {"M": 16, "efConstruction": 128}},
        )

    def _can_connect_port(self) -> bool:
        try:
            with socket.create_connection((self.host, int(self.port)), timeout=0.5):
                return True
        except OSError:
            return False
