from __future__ import annotations

import math
import re
from collections import defaultdict

from app.modules.graph_data_preparation import GraphDataPreparationModule, RecipeRecord
from app.modules.milvus_index_construction import MilvusIndexConstructionModule
from app.schemas.chat import Source


class HybridRetrievalModule:
    """Milvus semantic retrieval plus local keyword/entity fallback."""

    def __init__(
        self,
        graph_data: GraphDataPreparationModule,
        milvus_index: MilvusIndexConstructionModule,
    ):
        self.graph_data = graph_data
        self.milvus_index = milvus_index

    def search(self, query: str, limit: int = 5) -> tuple[list[RecipeRecord], list[Source]]:
        filters = self._query_filters(query)
        vector_hits = self.milvus_index.search(query, limit=limit * 2)
        keyword_hits = self._keyword_search(query, limit=limit * 2)
        ranked_ids = self._rrf(vector_hits, keyword_hits)

        records: list[RecipeRecord] = []
        sources: list[Source] = []
        for recipe_id, score in ranked_ids[:limit]:
            record = self.graph_data.get_recipe(recipe_id)
            if not record:
                continue
            if not self._matches_filters(record, filters):
                continue
            records.append(record)
            sources.append(
                Source(
                    recipe_id=record.id,
                    recipe_name=record.name,
                    category=record.category,
                    difficulty=record.difficulty,
                    score=score,
                )
            )
        return records, sources

    def _keyword_search(self, query: str, limit: int) -> list[dict]:
        tokens = self._tokens(query)
        filters = self._query_filters(query)
        scored: list[dict] = []
        for record in self.graph_data.get_records():
            if not self._matches_filters(record, filters):
                continue
            haystack = " ".join(
                [
                    record.name,
                    record.category,
                    record.difficulty,
                    record.description,
                    " ".join(item.name for item in record.ingredients),
                    " ".join(record.steps[:6]),
                ]
            )
            score = self._keyword_score(tokens, haystack)
            if score > 0:
                scored.append(
                    {
                        "recipe_id": record.id,
                        "recipe_name": record.name,
                        "score": score,
                    }
                )
        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:limit]

    def _query_filters(self, query: str) -> dict[str, str]:
        filters: dict[str, str] = {}
        for category in ("荤菜", "素菜", "汤品", "甜品", "早餐", "主食", "水产", "调料", "饮品", "半成品"):
            if category in query:
                filters["category"] = category
                break
        for difficulty in ("非常简单", "简单", "中等", "困难", "非常困难"):
            if difficulty in query:
                filters["difficulty"] = difficulty
                break
        return filters

    def _matches_filters(self, record: RecipeRecord, filters: dict[str, str]) -> bool:
        if filters.get("category") and record.category != filters["category"]:
            return False
        if filters.get("difficulty") and record.difficulty not in (filters["difficulty"], "未知"):
            return False
        return True

    def _tokens(self, query: str) -> list[str]:
        labels = [
            "荤菜",
            "素菜",
            "汤品",
            "甜品",
            "早餐",
            "主食",
            "水产",
            "调料",
            "饮品",
            "半成品",
            "非常简单",
            "简单",
            "中等",
            "困难",
        ]
        tokens = [label for label in labels if label in query]
        tokens.extend(re.findall(r"[a-zA-Z0-9]+", query))
        tokens.extend(re.findall(r"[\u4e00-\u9fff]{1,2}", query))
        return list(dict.fromkeys(token for token in tokens if token.strip()))

    def _keyword_score(self, tokens: list[str], text: str) -> float:
        score = 0.0
        for token in tokens:
            if token in text:
                score += 1.0 + math.log1p(text.count(token))
        return score

    def _rrf(self, vector_hits: list[dict], keyword_hits: list[dict], k: int = 60) -> list[tuple[str, float]]:
        scores: dict[str, float] = defaultdict(float)
        for rank, hit in enumerate(vector_hits):
            if hit.get("recipe_id"):
                scores[hit["recipe_id"]] += 1.0 / (k + rank + 1)
        for rank, hit in enumerate(keyword_hits):
            if hit.get("recipe_id"):
                scores[hit["recipe_id"]] += 1.0 / (k + rank + 1)
        return sorted(scores.items(), key=lambda item: item[1], reverse=True)
