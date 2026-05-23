from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QueryAnalysis:
    strategy: str
    complexity: str
    reason: str


class IntelligentQueryRouter:
    """Rules-first query routing for the first web version."""

    graph_keywords = ("我有", "不能", "不要", "不含", "替代", "搭配", "同时", "满足", "已有", "剩下")
    list_keywords = ("推荐", "有哪些", "几个", "什么菜", "吃什么", "简单")
    detail_keywords = ("怎么做", "做法", "步骤", "原料", "材料", "需要什么")

    def analyze(self, query: str) -> QueryAnalysis:
        normalized = query.strip()
        if any(keyword in normalized for keyword in self.graph_keywords):
            return QueryAnalysis("graph_rag", "high", "包含多条件或关系推理信号")
        if any(keyword in normalized for keyword in self.list_keywords):
            return QueryAnalysis("hybrid", "low", "推荐或列表型查询")
        if any(keyword in normalized for keyword in self.detail_keywords):
            return QueryAnalysis("hybrid", "low", "具体做法或材料查询")
        if len(normalized) > 40:
            return QueryAnalysis("combined", "medium", "较长查询，组合语义检索与图扩展")
        return QueryAnalysis("hybrid", "low", "默认混合检索")
