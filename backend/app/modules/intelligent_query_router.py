from __future__ import annotations

import re
from dataclasses import dataclass, field


CATEGORY_ALIASES: dict[str, tuple[str, ...]] = {
    "荤菜": ("荤菜", "肉菜", "肉类", "吃肉", "有肉"),
    "素菜": ("素菜", "蔬菜", "青菜", "素食", "素的", "不吃肉", "无肉"),
    "汤品": ("汤品", "汤", "煲汤", "炖汤", "粥"),
    "甜品": ("甜品", "甜点", "蛋糕", "甜食"),
    "早餐": ("早餐", "早饭", "早上"),
    "主食": ("主食", "米饭", "面条", "面食", "饭", "面"),
    "水产": ("水产", "海鲜", "鱼", "虾", "蟹", "生蚝"),
    "调料": ("调料", "酱料", "蘸料"),
    "饮品": ("饮品", "饮料", "喝的", "茶", "酒"),
    "半成品": ("半成品", "速冻", "空气炸锅"),
}

DIFFICULTY_ALIASES: dict[str, tuple[str, ...]] = {
    "非常简单": ("非常简单", "超简单", "特别简单", "零基础"),
    "简单": ("简单", "低难度", "容易", "快手", "新手", "懒人", "省事"),
    "中等": ("中等", "一般难度"),
    "困难": ("困难", "复杂", "有挑战"),
    "非常困难": ("非常困难", "特别难", "很难"),
}

DETAIL_KEYWORDS = ("怎么做", "做法", "步骤", "原料", "材料", "需要什么", "教程")
LIST_KEYWORDS = ("推荐", "有哪些", "几个", "什么菜", "吃什么", "能做什么")
RELATION_KEYWORDS = ("我有", "手边有", "已有", "剩下", "不能", "不要", "不含", "替代", "搭配", "同时", "满足")

STOPWORDS = (
    "推荐",
    "我有",
    "手边有",
    "已有",
    "剩下",
    "几个",
    "一些",
    "有什么",
    "什么",
    "能做",
    "能做什么",
    "可以做",
    "怎么做",
    "做法",
    "步骤",
    "原料",
    "材料",
    "需要",
    "不要",
    "不能",
    "不吃",
    "不含",
    "菜谱",
    "菜",
    "晚餐",
    "午餐",
    "早饭",
    "早餐",
    "简单",
    "低难度",
)


@dataclass(frozen=True)
class QueryAnalysis:
    strategy: str
    complexity: str
    reason: str
    intent: str = "recommend"
    include_terms: tuple[str, ...] = field(default_factory=tuple)
    exclude_terms: tuple[str, ...] = field(default_factory=tuple)
    query_terms: tuple[str, ...] = field(default_factory=tuple)
    category: str | None = None
    difficulty: str | None = None
    needs_steps: bool = False
    dish_only: bool = False


class IntelligentQueryRouter:
    """Rules-first query understanding and routing."""

    def analyze(self, query: str) -> QueryAnalysis:
        normalized = query.strip()
        category = self._category(normalized)
        difficulty = self._difficulty(normalized)
        include_terms = self._include_terms(normalized)
        exclude_terms = self._exclude_terms(normalized)
        needs_steps = any(keyword in normalized for keyword in DETAIL_KEYWORDS)
        intent = self._intent(normalized, needs_steps)
        dish_only = not category and any(keyword in normalized for keyword in ("菜", "吃", "午餐", "晚餐", "下饭"))
        query_terms = self._query_terms(normalized, include_terms, exclude_terms)

        constraint_count = sum(
            [
                bool(category),
                bool(difficulty),
                bool(include_terms),
                bool(exclude_terms),
            ]
        )
        if include_terms or exclude_terms:
            strategy = "graph_rag"
            complexity = "high"
            reason = "包含食材或排除条件，优先使用图结构约束检索"
        elif constraint_count >= 2 and intent != "recommend":
            strategy = "combined"
            complexity = "medium"
            reason = "包含多个筛选条件，组合图检索和混合检索"
        elif len(normalized) > 40:
            strategy = "combined"
            complexity = "medium"
            reason = "较长查询，组合语义检索与图扩展"
        else:
            strategy = "hybrid"
            complexity = "low"
            reason = "推荐、做法或普通关键词查询"

        return QueryAnalysis(
            strategy=strategy,
            complexity=complexity,
            reason=reason,
            intent=intent,
            include_terms=include_terms,
            exclude_terms=exclude_terms,
            query_terms=query_terms,
            category=category,
            difficulty=difficulty,
            needs_steps=needs_steps,
            dish_only=dish_only,
        )

    def _intent(self, query: str, needs_steps: bool) -> str:
        if needs_steps:
            return "detail"
        if any(keyword in query for keyword in LIST_KEYWORDS):
            return "recommend"
        if any(keyword in query for keyword in RELATION_KEYWORDS):
            return "constraint"
        return "search"

    def _category(self, query: str) -> str | None:
        for category, aliases in CATEGORY_ALIASES.items():
            if any(alias in query for alias in aliases):
                return category
        return None

    def _difficulty(self, query: str) -> str | None:
        for difficulty, aliases in DIFFICULTY_ALIASES.items():
            if any(alias in query for alias in aliases):
                return difficulty
        return None

    def _include_terms(self, query: str) -> tuple[str, ...]:
        terms: list[str] = []
        patterns = (
            r"(?:我有|手边有|已有|剩下)([^，。；,.!?？]+)",
            r"有([^，。；,.!?？]+?)(?:能|可以|做|推荐|怎么|$)",
            r"(?:用|包含|带)([^，。；,.!?？]+?)(?:做|推荐|的|$)",
        )
        for pattern in patterns:
            for match in re.finditer(pattern, query):
                terms.extend(self._split_terms(match.group(1)))
        return self._dedupe(terms)

    def _exclude_terms(self, query: str) -> tuple[str, ...]:
        terms: list[str] = []
        patterns = (
            r"(?:不要|不吃|不能吃|不含|忌口|避免|去掉)([^，。；,.!?？]+)",
            r"无([^，。；,.!?？]+)",
        )
        for pattern in patterns:
            for match in re.finditer(pattern, query):
                terms.extend(self._split_terms(match.group(1)))
        expanded: list[str] = []
        for term in terms:
            expanded.append(term)
            if term in ("辣", "辣椒"):
                expanded.extend(["辣", "辣椒", "小米辣", "干辣椒", "剁椒", "豆瓣酱"])
        return self._dedupe(expanded)

    def _query_terms(
        self,
        query: str,
        include_terms: tuple[str, ...],
        exclude_terms: tuple[str, ...],
    ) -> tuple[str, ...]:
        cleaned = query
        for aliases in CATEGORY_ALIASES.values():
            for alias in aliases:
                cleaned = cleaned.replace(alias, " ")
        for aliases in DIFFICULTY_ALIASES.values():
            for alias in aliases:
                cleaned = cleaned.replace(alias, " ")
        for word in STOPWORDS:
            cleaned = cleaned.replace(word, " ")
        for term in include_terms + exclude_terms:
            cleaned = cleaned.replace(term, " ")

        terms = list(include_terms)
        for fragment in re.findall(r"[\u4e00-\u9fff]{2,8}|[a-zA-Z0-9]+", cleaned):
            if fragment in STOPWORDS:
                continue
            terms.append(fragment)
            if re.fullmatch(r"[\u4e00-\u9fff]{5,8}", fragment):
                for size in (4, 3, 2):
                    terms.extend(fragment[index : index + size] for index in range(0, len(fragment) - size + 1))
        return self._dedupe(term for term in terms if len(term) >= 2)

    def _split_terms(self, text: str) -> list[str]:
        normalized = re.sub(r"[和与及、/，,；;]", " ", text)
        raw_terms = re.findall(r"[\u4e00-\u9fff]{1,8}|[a-zA-Z0-9]+", normalized)
        cleaned: list[str] = []
        for term in raw_terms:
            item = term.strip()
            for word in STOPWORDS:
                item = item.replace(word, "")
            item = item.strip("的了吧吗呢 ")
            if item and item not in STOPWORDS:
                cleaned.append(item)
        return cleaned

    def _dedupe(self, terms) -> tuple[str, ...]:
        result: list[str] = []
        for term in terms:
            if term and term not in result:
                result.append(term)
        return tuple(result)
