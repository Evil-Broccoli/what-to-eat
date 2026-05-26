from __future__ import annotations

from dataclasses import dataclass

from app.modules.graph_data_preparation import RecipeRecord
from app.modules.intelligent_query_router import QueryAnalysis
from app.schemas.chat import Source


EASY_DIFFICULTIES = ("非常简单", "简单", "未知")
NON_DISH_CATEGORIES = ("饮品", "调料", "半成品")


@dataclass(frozen=True)
class RecordMatch:
    score: float
    reason: str
    matched_terms: tuple[str, ...]


def difficulty_levels(analysis: QueryAnalysis) -> tuple[str, ...]:
    if not analysis.difficulty:
        return ()
    if analysis.difficulty in ("非常简单", "简单"):
        return EASY_DIFFICULTIES
    return (analysis.difficulty, "未知")


def record_text(record: RecipeRecord, include_steps: bool = True) -> str:
    parts = [
        record.name,
        record.category,
        record.difficulty,
        record.description,
        " ".join(item.name for item in record.ingredients),
    ]
    if include_steps:
        parts.append(" ".join(record.steps[:8]))
    return " ".join(part for part in parts if part)


def match_record(record: RecipeRecord, analysis: QueryAnalysis) -> RecordMatch | None:
    if analysis.category and record.category != analysis.category:
        return None
    if analysis.dish_only and record.category in NON_DISH_CATEGORIES:
        return None

    allowed_difficulties = difficulty_levels(analysis)
    if allowed_difficulties and record.difficulty not in allowed_difficulties:
        return None

    text = record_text(record)
    ingredient_names = [item.name for item in record.ingredients]
    if any(term and term in text for term in analysis.exclude_terms):
        return None

    score = 0.0
    reasons: list[str] = []
    matched_terms: list[str] = []

    if analysis.category:
        score += 4.0
        reasons.append(f"匹配类别：{analysis.category}")
        matched_terms.append(analysis.category)

    if analysis.difficulty:
        score += 3.0 if record.difficulty == analysis.difficulty else 2.0
        reasons.append(f"匹配难度：{record.difficulty}")
        matched_terms.append(record.difficulty)

    include_hits = _term_hits(analysis.include_terms, record, ingredient_names, text)
    if analysis.include_terms and not include_hits:
        return None
    if include_hits:
        score += sum(weight for _, weight in include_hits)
        terms = [term for term, _ in include_hits]
        reasons.append(f"命中食材：{'、'.join(terms[:4])}")
        matched_terms.extend(terms)

    query_hits = _term_hits(analysis.query_terms, record, ingredient_names, text)
    if query_hits:
        score += sum(weight * 0.6 for _, weight in query_hits)
        matched_terms.extend(term for term, _ in query_hits)
        if not include_hits:
            reasons.append(f"命中关键词：{'、'.join([term for term, _ in query_hits[:4]])}")

    if analysis.needs_steps and (record.steps or any(term in record.name for term in analysis.query_terms)):
        score += 2.0
        reasons.append("适合查看做法步骤")

    if record.name in analysis.query_terms or any(term in record.name for term in analysis.query_terms):
        score += 3.0

    if not reasons and score <= 0:
        return None

    reason = "；".join(dict.fromkeys(reasons)) or "匹配菜名、食材或做法关键词"
    return RecordMatch(score=score, reason=reason, matched_terms=_dedupe(matched_terms))


def source_from_match(record: RecipeRecord, match: RecordMatch, score: float | None = None) -> Source:
    return Source(
        recipe_id=record.id,
        recipe_name=record.name,
        category=record.category,
        difficulty=record.difficulty,
        score=round(score if score is not None else match.score, 4),
        reason=match.reason,
        matched_terms=list(match.matched_terms),
    )


def _term_hits(
    terms: tuple[str, ...],
    record: RecipeRecord,
    ingredient_names: list[str],
    text: str,
) -> list[tuple[str, float]]:
    hits: list[tuple[str, float]] = []
    for term in terms:
        if not term:
            continue
        if term in record.name:
            hits.append((term, 7.0))
        elif any(term in name for name in ingredient_names):
            hits.append((term, 6.0))
        elif term in record.description:
            hits.append((term, 2.0))
        elif term in text:
            hits.append((term, 1.0))
    return hits


def _dedupe(items: list[str]) -> tuple[str, ...]:
    result: list[str] = []
    for item in items:
        if item and item not in result:
            result.append(item)
    return tuple(result[:8])
