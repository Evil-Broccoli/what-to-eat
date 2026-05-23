from __future__ import annotations

from datetime import datetime, timezone

from app.core.config import settings
from app.modules.generation_integration import GenerationIntegrationModule
from app.modules.graph_data_preparation import GraphDataPreparationModule
from app.modules.graph_rag_retrieval import GraphRAGRetrieval
from app.modules.hybrid_retrieval import HybridRetrievalModule
from app.modules.intelligent_query_router import IntelligentQueryRouter
from app.modules.milvus_index_construction import MilvusIndexConstructionModule
from app.schemas.chat import ChatResponse, IndexStatus, RebuildResponse
from app.schemas.recipe import RecipeDetail, RecipeListResponse


class RagService:
    def __init__(self):
        self.graph_data = GraphDataPreparationModule(
            data_path=settings.data_path,
            neo4j_uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password,
        )
        self.milvus_index = MilvusIndexConstructionModule(
            host=settings.milvus_host,
            port=settings.milvus_port,
            collection_name=settings.milvus_collection,
            model_name=settings.embedding_model,
        )
        self.router = IntelligentQueryRouter()
        self.hybrid = HybridRetrievalModule(self.graph_data, self.milvus_index)
        self.graph_rag = GraphRAGRetrieval(self.graph_data)
        self.generator = GenerationIntegrationModule(
            api_key=settings.openai_api_key,
            model_name=settings.llm_model,
            max_context_chars=settings.max_context_chars,
            base_url=settings.openai_base_url,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )
        self.last_build: str | None = None
        self.graph_data.load_from_markdown()

    def health(self) -> IndexStatus:
        records = self.graph_data.get_records()
        chunks = self.graph_data.build_chunks(records)
        return IndexStatus(
            neo4j=self.graph_data.is_neo4j_available,
            milvus=self.milvus_index.is_available,
            recipe_count=len(records),
            chunk_count=self.milvus_index.count() or len(chunks),
            last_build=self.last_build,
        )

    def rebuild(self) -> RebuildResponse:
        records = self.graph_data.load_from_markdown()
        failed = self.graph_data.sync_to_neo4j(records)
        chunks = self.graph_data.build_chunks(records)
        indexed = self.milvus_index.rebuild(chunks)
        self.last_build = datetime.now(timezone.utc).isoformat()
        status = self.health()
        return RebuildResponse(
            **status.model_dump(),
            chunk_count=indexed or len(chunks),
            message="索引重建完成；不可用的外部服务已使用本地 Markdown 兜底。" if failed or not indexed else "索引重建完成。",
            failed_sources=failed,
        )

    def chat(self, query: str) -> ChatResponse:
        analysis = self.router.analyze(query)
        try:
            if analysis.strategy == "graph_rag":
                records, sources = self.graph_rag.search(query, limit=settings.top_k)
            elif analysis.strategy == "combined":
                graph_records, graph_sources = self.graph_rag.search(query, limit=settings.top_k)
                hybrid_records, hybrid_sources = self.hybrid.search(query, limit=settings.top_k)
                records = self._dedupe_records(graph_records + hybrid_records)
                sources = self._dedupe_sources(graph_sources + hybrid_sources)
            else:
                records, sources = self.hybrid.search(query, limit=settings.top_k)
        except Exception:
            records, sources = self.hybrid.search(query, limit=settings.top_k)
            analysis = self.router.analyze("推荐")

        answer = self.generator.generate(query, records, analysis.strategy)
        return ChatResponse(answer=answer, strategy=analysis.strategy, sources=sources)

    def stream_chat(self, query: str):
        response = self.chat(query)
        for token in self.generator.stream(query, self._records_from_sources(response.sources), response.strategy):
            yield token

    def list_recipes(
        self,
        category: str | None = None,
        difficulty: str | None = None,
        q: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> RecipeListResponse:
        records = self.graph_data.get_records()
        if category:
            records = [record for record in records if record.category == category]
        if difficulty:
            records = [record for record in records if record.difficulty == difficulty]
        if q:
            records = [
                record
                for record in records
                if q in record.name
                or q in record.description
                or any(q in item.name for item in record.ingredients)
            ]
        total = len(records)
        items = [record.summary() for record in records[offset : offset + limit]]
        return RecipeListResponse(items=items, total=total)

    def get_recipe(self, recipe_id: str) -> RecipeDetail | None:
        record = self.graph_data.get_recipe(recipe_id)
        if not record:
            return None
        return record.detail(related=self.graph_data.find_related(record))

    def _records_from_sources(self, sources):
        return [record for source in sources if (record := self.graph_data.get_recipe(source.recipe_id))]

    def _dedupe_records(self, records):
        seen = set()
        result = []
        for record in records:
            if record.id in seen:
                continue
            seen.add(record.id)
            result.append(record)
        return result

    def _dedupe_sources(self, sources):
        seen = set()
        result = []
        for source in sources:
            if source.recipe_id in seen:
                continue
            seen.add(source.recipe_id)
            result.append(source)
        return result


rag_service = RagService()
