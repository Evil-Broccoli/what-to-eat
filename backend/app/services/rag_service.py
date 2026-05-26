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
            dimension=settings.embedding_dimension,
            api_key=settings.embedding_api_key,
            base_url=settings.embedding_base_url,
            batch_size=settings.embedding_batch_size,
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
        neo4j_available = self.graph_data.is_neo4j_available
        milvus_available = self.milvus_index.is_available
        degraded_services = self._degraded_services(neo4j_available, milvus_available)
        return IndexStatus(
            neo4j=neo4j_available,
            milvus=milvus_available,
            recipe_count=len(records),
            chunk_count=self.milvus_index.count() if milvus_available else len(chunks),
            last_build=self.last_build,
            llm_configured=self.generator.is_configured,
            llm_model=self.generator.model_name,
            embedding_configured=self.milvus_index.is_embedding_configured,
            embedding_model=self.milvus_index.model_name,
            embedding_dimension=self.milvus_index.dimension,
            degraded_services=degraded_services,
        )

    def rebuild(self) -> RebuildResponse:
        records = self.graph_data.load_from_markdown()
        failed = self.graph_data.sync_to_neo4j(records)
        chunks = self.graph_data.build_chunks(records)
        indexed = self.milvus_index.rebuild(chunks)
        if not indexed and chunks:
            reason = self.milvus_index.fallback_reason()
            if reason:
                failed.append(reason)
        self.last_build = datetime.now(timezone.utc).isoformat()
        status = self.health()
        payload = status.model_dump()
        payload["chunk_count"] = indexed or len(chunks)
        return RebuildResponse(
            **payload,
            message="索引重建完成；不可用的外部服务已使用本地 Markdown 兜底。" if failed or not indexed else "索引重建完成。",
            failed_sources=failed,
        )

    def chat(self, query: str) -> ChatResponse:
        records, sources, strategy = self.retrieve(query)
        answer = self.generator.generate(query, records, strategy)
        return ChatResponse(answer=answer, strategy=strategy, sources=sources)

    def retrieve(self, query: str):
        analysis = self.router.analyze(query)
        try:
            if analysis.strategy == "graph_rag":
                records, sources = self.graph_rag.search(query, limit=settings.top_k, analysis=analysis)
            elif analysis.strategy == "combined":
                _, graph_sources = self.graph_rag.search(query, limit=settings.top_k, analysis=analysis)
                _, hybrid_sources = self.hybrid.search(query, limit=settings.top_k, analysis=analysis)
                sources = self._dedupe_sources(graph_sources + hybrid_sources)[: settings.top_k]
                records = self._records_from_sources(sources)
            else:
                records, sources = self.hybrid.search(query, limit=settings.top_k, analysis=analysis)
        except Exception:
            records, sources = self.hybrid.search(query, limit=settings.top_k, analysis=analysis)
            return records, sources, "hybrid"

        return records, sources, analysis.strategy

    def stream_chat(self, query: str):
        records, sources, strategy = self.retrieve(query)
        yield "meta", {"strategy": strategy, "sources": [item.model_dump() for item in sources]}
        for token in self.stream_answer(query, records, strategy):
            yield "token", {"content": token}
        yield "done", {}

    def stream_answer(self, query: str, records, strategy: str):
        yield from self.generator.stream(query, records, strategy)

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
        by_id = {}
        for source in sources:
            existing = by_id.get(source.recipe_id)
            if existing and existing.score >= source.score:
                continue
            by_id[source.recipe_id] = source
        return sorted(by_id.values(), key=lambda item: item.score, reverse=True)

    def _degraded_services(self, neo4j_available: bool, milvus_available: bool) -> list[str]:
        messages: list[str] = []
        if not neo4j_available:
            messages.append("Neo4j 未连接，图谱同步和图遍历会使用本地 Markdown 兜底")
        if not milvus_available:
            reason = self.milvus_index.fallback_reason()
            messages.append(reason or "Milvus 不可用，向量检索会使用本地关键词兜底")
        llm_reason = self.generator.fallback_reason
        if llm_reason:
            messages.append(llm_reason)
        return list(dict.fromkeys(messages))


rag_service = RagService()
