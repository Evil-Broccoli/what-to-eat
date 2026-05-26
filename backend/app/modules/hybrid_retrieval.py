from __future__ import annotations

from collections import defaultdict

from app.modules.graph_data_preparation import GraphDataPreparationModule, RecipeRecord
from app.modules.intelligent_query_router import IntelligentQueryRouter, QueryAnalysis
from app.modules.milvus_index_construction import MilvusIndexConstructionModule
from app.modules.retrieval_scoring import match_record, source_from_match
from app.schemas.chat import Source


class HybridRetrievalModule:
    """Milvus semantic retrieval plus structured keyword/entity ranking."""

    def __init__(
        self,
        graph_data: GraphDataPreparationModule,
        milvus_index: MilvusIndexConstructionModule,
    ):
        self.graph_data = graph_data
        self.milvus_index = milvus_index
        self.router = IntelligentQueryRouter()

    def search(
        self,
        query: str,
        limit: int = 5,
        analysis: QueryAnalysis | None = None,
    ) -> tuple[list[RecipeRecord], list[Source]]:
        analysis = analysis or self.router.analyze(query)
        vector_hits = self.milvus_index.search(query, limit=limit * 4)
        keyword_hits = self._keyword_search(analysis, limit=limit * 4)
        ranked_ids = self._rank(vector_hits, keyword_hits)

        records: list[RecipeRecord] = []
        sources: list[Source] = []
        for recipe_id, score in ranked_ids:
            record = self.graph_data.get_recipe(recipe_id)
            if not record or any(item.id == record.id for item in records):
                continue
            match = match_record(record, analysis)
            if not match:
                continue
            records.append(record)
            sources.append(source_from_match(record, match, score=max(score, match.score)))
            if len(records) >= limit:
                break

        if len(records) < limit:
            self._append_fallback_matches(analysis, records, sources, limit)
        return records, sources

    def _keyword_search(self, analysis: QueryAnalysis, limit: int) -> list[dict]:
        scored: list[dict] = []
        for record in self.graph_data.get_records():
            match = match_record(record, analysis)
            if not match:
                continue
            scored.append(
                {
                    "recipe_id": record.id,
                    "recipe_name": record.name,
                    "score": match.score,
                    "matched_terms": list(match.matched_terms),
                    "reason": match.reason,
                }
            )
        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:limit]

    def _rank(self, vector_hits: list[dict], keyword_hits: list[dict], k: int = 60) -> list[tuple[str, float]]:
        scores: dict[str, float] = defaultdict(float)
        for rank, hit in enumerate(vector_hits):
            if hit.get("recipe_id"):
                scores[hit["recipe_id"]] += 10.0 / (k + rank + 1)
        for rank, hit in enumerate(keyword_hits):
            if hit.get("recipe_id"):
                scores[hit["recipe_id"]] += float(hit.get("score", 0)) + 10.0 / (k + rank + 1)
        return sorted(scores.items(), key=lambda item: item[1], reverse=True)

    def _append_fallback_matches(
        self,
        analysis: QueryAnalysis,
        records: list[RecipeRecord],
        sources: list[Source],
        limit: int,
    ) -> None:
        seen = {record.id for record in records}
        matches: list[tuple[float, RecipeRecord]] = []
        for record in self.graph_data.get_records():
            if record.id in seen:
                continue
            match = match_record(record, analysis)
            if match:
                matches.append((match.score, record))
        matches.sort(key=lambda item: item[0], reverse=True)
        for score, record in matches:
            match = match_record(record, analysis)
            if not match:
                continue
            records.append(record)
            sources.append(source_from_match(record, match, score=score))
            if len(records) >= limit:
                break
