from __future__ import annotations

from app.modules.graph_data_preparation import GraphDataPreparationModule, RecipeRecord
from app.modules.intelligent_query_router import IntelligentQueryRouter, QueryAnalysis
from app.modules.retrieval_scoring import difficulty_levels, match_record, source_from_match
from app.schemas.chat import Source


class GraphRAGRetrieval:
    """Graph-aware retrieval with a local fallback over structured records."""

    def __init__(self, graph_data: GraphDataPreparationModule):
        self.graph_data = graph_data
        self.router = IntelligentQueryRouter()

    def search(
        self,
        query: str,
        limit: int = 5,
        analysis: QueryAnalysis | None = None,
    ) -> tuple[list[RecipeRecord], list[Source]]:
        analysis = analysis or self.router.analyze(query)
        if self.graph_data.is_neo4j_available:
            records = self._search_neo4j(analysis, limit * 3)
        else:
            records = []

        if len(records) < limit:
            records = self._merge_records(records, self._search_local(analysis, limit * 3))

        ranked: list[tuple[float, RecipeRecord, Source]] = []
        for record in records:
            match = match_record(record, analysis)
            if not match:
                continue
            ranked.append((match.score, record, source_from_match(record, match)))
        ranked.sort(key=lambda item: item[0], reverse=True)
        top = ranked[:limit]
        return [record for _, record, _ in top], [source for _, _, source in top]

    def _search_neo4j(self, analysis: QueryAnalysis, limit: int) -> list[RecipeRecord]:
        try:
            with self.graph_data.driver.session() as session:
                rows = session.run(
                    """
                    MATCH (r:Recipe)
                    OPTIONAL MATCH (r)-[:HAS_INGREDIENT]->(i:Ingredient)
                    WITH r, collect(coalesce(i.name, "")) AS ingredient_names
                    WHERE ($category IS NULL OR r.category = $category)
                      AND ($difficulty_levels = [] OR r.difficulty IN $difficulty_levels)
                      AND (
                        $include_terms = []
                        OR any(term IN $include_terms WHERE
                          r.name CONTAINS term
                          OR coalesce(r.description, "") CONTAINS term
                          OR any(name IN ingredient_names WHERE name CONTAINS term)
                        )
                      )
                      AND (
                        $exclude_terms = []
                        OR none(term IN $exclude_terms WHERE
                          r.name CONTAINS term
                          OR coalesce(r.description, "") CONTAINS term
                          OR any(name IN ingredient_names WHERE name CONTAINS term)
                        )
                      )
                    WITH r, ingredient_names,
                      size([term IN $include_terms WHERE
                        r.name CONTAINS term
                        OR any(name IN ingredient_names WHERE name CONTAINS term)
                      ]) AS include_hits,
                      size([term IN $query_terms WHERE
                        r.name CONTAINS term
                        OR any(name IN ingredient_names WHERE name CONTAINS term)
                      ]) AS query_hits
                    RETURN r.id AS id, include_hits * 5 + query_hits * 2 AS graph_score
                    ORDER BY graph_score DESC, r.name ASC
                    LIMIT $limit
                    """,
                    category=analysis.category,
                    difficulty_levels=list(difficulty_levels(analysis)),
                    include_terms=list(analysis.include_terms),
                    exclude_terms=list(analysis.exclude_terms),
                    query_terms=list(analysis.query_terms),
                    limit=limit,
                )
                ids = [row["id"] for row in rows]
        except Exception:
            return []

        records = [self.graph_data.get_recipe(recipe_id) for recipe_id in ids]
        return [record for record in records if record]

    def _search_local(self, analysis: QueryAnalysis, limit: int) -> list[RecipeRecord]:
        scored: list[tuple[float, RecipeRecord]] = []
        for record in self.graph_data.get_records():
            match = match_record(record, analysis)
            if match:
                scored.append((match.score, record))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [record for _, record in scored[:limit]]

    def _merge_records(self, first: list[RecipeRecord], second: list[RecipeRecord]) -> list[RecipeRecord]:
        seen: set[str] = set()
        result: list[RecipeRecord] = []
        for record in first + second:
            if record.id in seen:
                continue
            seen.add(record.id)
            result.append(record)
        return result
