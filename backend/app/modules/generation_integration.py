from __future__ import annotations

import logging

from app.modules.graph_data_preparation import RecipeRecord

try:
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_openai import ChatOpenAI
except ImportError:  # pragma: no cover - optional dependency
    ChatOpenAI = ChatPromptTemplate = StrOutputParser = None

logger = logging.getLogger(__name__)


class GenerationIntegrationModule:
    """Generates final answers from retrieved recipe records."""

    def __init__(
        self,
        api_key: str | None,
        model_name: str,
        max_context_chars: int,
        base_url: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ):
        self.api_key = api_key
        self.model_name = model_name
        self.max_context_chars = max_context_chars
        self.base_url = base_url
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._llm = None

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.model_name and ChatOpenAI is not None)

    @property
    def fallback_reason(self) -> str | None:
        if ChatOpenAI is None:
            return "langchain-openai 未安装，问答会使用检索结果模板兜底"
        if not self.api_key:
            return "LLM API Key 未配置，问答会使用检索结果模板兜底"
        if not self.model_name:
            return "LLM 模型名未配置，问答会使用检索结果模板兜底"
        return None

    @property
    def llm(self):
        if not self.api_key or ChatOpenAI is None:
            return None
        if self._llm is None:
            self._llm = ChatOpenAI(
                model=self.model_name,
                api_key=self.api_key,
                base_url=self.base_url,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
        return self._llm

    def generate(self, query: str, records: list[RecipeRecord], strategy: str) -> str:
        if not records:
            return "抱歉，暂时没有找到匹配的菜谱。可以换一个菜名、食材或条件再试。"

        chain = self._chain()
        if chain:
            try:
                return chain.invoke(self._payload(query, records, strategy))
            except Exception as exc:
                logger.warning("LLM generation failed, using fallback: %s", exc)
        return self._fallback_answer(query, records)

    def stream(self, query: str, records: list[RecipeRecord], strategy: str):
        if not records:
            yield "抱歉，暂时没有找到匹配的菜谱。可以换一个菜名、食材或条件再试。"
            return

        chain = self._chain()
        if chain:
            try:
                for chunk in chain.stream(self._payload(query, records, strategy)):
                    if chunk:
                        yield str(chunk)
                return
            except Exception as exc:
                logger.warning("LLM streaming failed, using fallback: %s", exc)

        for char in self._fallback_answer(query, records):
            yield char

    def _chain(self):
        llm = self.llm
        if not llm or not ChatPromptTemplate or not StrOutputParser:
            return None
        return self._prompt() | llm | StrOutputParser()

    def _payload(self, query: str, records: list[RecipeRecord], strategy: str) -> dict[str, str]:
        return {"query": query, "strategy": strategy, "context": self._context(records)}

    def _prompt(self):
        return ChatPromptTemplate.from_template(
            """
你是一个专业、实用的中文烹饪助手。请基于给定菜谱资料回答用户问题。

用户问题：{query}
检索策略：{strategy}

菜谱资料：
{context}

要求：
- 如果用户要推荐，只给出合适菜品并说明理由。
- 如果用户问做法，按食材、步骤、技巧组织。
- 不要编造资料中不存在的关键用量；信息不足时明确说明。

回答：
"""
        )

    def _context(self, records: list[RecipeRecord]) -> str:
        parts: list[str] = []
        used = 0
        for record in records:
            ingredients = "、".join(
                f"{item.name}{' ' + item.amount if item.amount else ''}" for item in record.ingredients[:20]
            )
            steps = "\n".join(f"{index + 1}. {step}" for index, step in enumerate(record.steps[:12]))
            text = (
                f"【{record.name}】分类：{record.category}；难度：{record.difficulty}\n"
                f"简介：{record.description}\n"
                f"原料：{ingredients}\n"
                f"步骤：\n{steps}\n"
            )
            if used + len(text) > self.max_context_chars:
                break
            parts.append(text)
            used += len(text)
        return "\n---\n".join(parts)

    def _fallback_answer(self, query: str, records: list[RecipeRecord]) -> str:
        if any(word in query for word in ("推荐", "有哪些", "吃什么", "能做什么")):
            lines = ["可以优先考虑这些菜："]
            for record in records[:5]:
                reason = record.description or f"{record.category}，难度 {record.difficulty}"
                lines.append(f"- {record.name}：{reason}")
            return "\n".join(lines)

        record = records[0]
        lines = [f"## {record.name}", f"分类：{record.category}；难度：{record.difficulty}"]
        if record.ingredients:
            lines.append("\n### 所需食材")
            lines.extend(f"- {item.name}{'：' + item.amount if item.amount else ''}" for item in record.ingredients[:20])
        if record.steps:
            lines.append("\n### 制作步骤")
            lines.extend(f"{index + 1}. {step}" for index, step in enumerate(record.steps[:12]))
        if not record.ingredients and not record.steps:
            lines.append(record.description or record.raw_text[:600])
        return "\n".join(lines)
