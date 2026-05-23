from __future__ import annotations

import re

from app.modules.graph_data_preparation import GraphDataPreparationModule, RecipeRecord
from app.schemas.chat import Source


class GraphRAGRetrieval:
    """Graph-aware retrieval with a local fallback over structured records."""

    def __init__(self, graph_data: GraphDataPreparationModule):
        self.graph_data = graph_data

    def search(self, query: str, limit: int = 5) -> tuple[list[RecipeRecord], list[Source]]:
        if self.graph_data.is_neo4j_available:
            records = self._search_neo4j(query, limit)
        else:
            records = self._search_local(query, limit)
        sources = [
            Source(
                recipe_id=record.id,
                recipe_name=record.name,
                category=record.category,
                difficulty=record.difficulty,
                score=max(0.1, 1 - index * 0.1),
            )
            for index, record in enumerate(records)
        ]
        return records, sources

    def _search_neo4j(self, query: str, limit: int) -> list[RecipeRecord]:
        entities = self._entities(query)
        if not entities:
            return self._search_local(query, limit)
        try:
            with self.graph_data.driver.session() as session:
                rows = session.run(
                    """
                    MATCH (r:Recipe)-[:HAS_INGREDIENT]->(i:Ingredient)
                    WHERE any(entity IN $entities WHERE i.name CONTAINS entity OR r.name CONTAINS entity)
                    RETURN DISTINCT r.id AS id
                    LIMIT $limit
                    """,
                    entities=entities,
                    limit=limit,
                )
                ids = [row["id"] for row in rows]
            records = [self.graph_data.get_recipe(recipe_id) for recipe_id in ids]
            return [record for record in records if record]
        except Exception:
            return self._search_local(query, limit)

    def _search_local(self, query: str, limit: int) -> list[RecipeRecord]:
        entities = self._entities(query)
        avoid_spicy = any(word in query for word in ("不要辣", "不辣", "不能吃辣"))
        easy_only = "简单" in query or "低难度" in query
        scored: list[tuple[int, RecipeRecord]] = []
        for record in self.graph_data.get_records():
            text = " ".join(
                [
                    record.name,
                    record.category,
                    record.difficulty,
                    record.description,
                    " ".join(item.name for item in record.ingredients),
                ]
            )
            if avoid_spicy and "辣" in text:
                continue
            if easy_only and record.difficulty not in ("非常简单", "简单", "未知"):
                continue
            score = sum(1 for entity in entities if entity in text)
            if score or not entities:
                scored.append((score, record))
        scored.sort(key=lambda item: (item[0], item[1].category), reverse=True)
        return [record for _, record in scored[:limit]]

    def _entities(self, query: str) -> list[str]:
        stopwords = {"我有", "能做什么", "推荐", "不要", "不能", "简单", "晚餐", "午餐", "早餐"}
        cleaned = query
        for word in stopwords:
            cleaned = cleaned.replace(word, " ")
        return [item for item in re.findall(r"[\u4e00-\u9fff]{1,4}", cleaned) if len(item) >= 1]
