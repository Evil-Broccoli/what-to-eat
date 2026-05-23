from __future__ import annotations

import hashlib
import logging
import re
import socket
from dataclasses import dataclass, field
from pathlib import Path

from app.schemas.recipe import Ingredient, RecipeDetail, RecipeSummary

try:
    from neo4j import GraphDatabase
except ImportError:  # pragma: no cover - optional dependency
    GraphDatabase = None

logger = logging.getLogger(__name__)


CATEGORY_MAPPING = {
    "meat_dish": "荤菜",
    "vegetable_dish": "素菜",
    "soup": "汤品",
    "dessert": "甜品",
    "breakfast": "早餐",
    "staple": "主食",
    "aquatic": "水产",
    "condiment": "调料",
    "drink": "饮品",
    "semi-finished": "半成品",
}


@dataclass
class RecipeRecord:
    id: str
    name: str
    category: str
    difficulty: str
    source: str
    description: str
    ingredients: list[Ingredient] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    sections: dict[str, str] = field(default_factory=dict)
    raw_text: str = ""

    def summary(self) -> RecipeSummary:
        return RecipeSummary(
            id=self.id,
            name=self.name,
            category=self.category,
            difficulty=self.difficulty,
            source=self.source,
            description=self.description,
        )

    def detail(self, related: list[RecipeSummary] | None = None) -> RecipeDetail:
        return RecipeDetail(
            **self.summary().model_dump(),
            ingredients=self.ingredients,
            steps=self.steps,
            sections=self.sections,
            related=related or [],
        )


class GraphDataPreparationModule:
    """Loads markdown recipes, syncs them to Neo4j, and produces structured docs."""

    def __init__(self, data_path: Path, neo4j_uri: str, user: str, password: str):
        self.data_path = Path(data_path)
        self.neo4j_uri = neo4j_uri
        self.user = user
        self.password = password
        self.records: list[RecipeRecord] = []
        self._driver = None

    @property
    def is_neo4j_available(self) -> bool:
        if GraphDatabase is None:
            return False
        if not self._can_connect_port():
            return False
        try:
            driver = self.driver
            with driver.session() as session:
                session.run("RETURN 1 AS ok").single()
            return True
        except Exception:
            return False

    @property
    def driver(self):
        if GraphDatabase is None:
            raise RuntimeError("neo4j package is not installed")
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                self.neo4j_uri,
                auth=(self.user, self.password),
                connection_timeout=2,
            )
        return self._driver

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def load_from_markdown(self) -> list[RecipeRecord]:
        records: list[RecipeRecord] = []
        for md_file in self.data_path.rglob("*.md"):
            try:
                text = md_file.read_text(encoding="utf-8")
                records.append(self._parse_markdown(md_file, text))
            except Exception as exc:
                logger.warning("Failed to parse %s: %s", md_file, exc)
        self.records = records
        return records

    def sync_to_neo4j(self, records: list[RecipeRecord] | None = None) -> list[str]:
        records = records or self.records
        failed: list[str] = []
        if not self.is_neo4j_available:
            return [record.source for record in records]

        with self.driver.session() as session:
            self._ensure_constraints(session)
            for record in records:
                try:
                    session.execute_write(self._write_recipe, record)
                except Exception as exc:
                    logger.warning("Failed to sync %s: %s", record.source, exc)
                    failed.append(record.source)
        return failed

    def get_records(self) -> list[RecipeRecord]:
        if not self.records:
            return self.load_from_markdown()
        return self.records

    def get_recipe(self, recipe_id: str) -> RecipeRecord | None:
        return next((record for record in self.get_records() if record.id == recipe_id), None)

    def find_related(self, recipe: RecipeRecord, limit: int = 4) -> list[RecipeSummary]:
        recipe_ingredients = {item.name for item in recipe.ingredients}
        candidates: list[tuple[int, RecipeRecord]] = []
        for other in self.get_records():
            if other.id == recipe.id:
                continue
            overlap = len(recipe_ingredients & {item.name for item in other.ingredients})
            category_bonus = 1 if other.category == recipe.category else 0
            score = overlap * 2 + category_bonus
            if score > 0:
                candidates.append((score, other))
        candidates.sort(key=lambda item: item[0], reverse=True)
        return [record.summary() for _, record in candidates[:limit]]

    def build_chunks(self, records: list[RecipeRecord] | None = None) -> list[dict]:
        chunks: list[dict] = []
        for record in records or self.get_records():
            if record.description:
                chunks.append(self._chunk(record, "description", record.description))
            for title, content in record.sections.items():
                if content.strip():
                    chunks.append(self._chunk(record, title, content))
            if not record.sections:
                chunks.append(self._chunk(record, "full", record.raw_text[:4000]))
        return chunks

    def _parse_markdown(self, path: Path, text: str) -> RecipeRecord:
        relative_path = path.resolve().relative_to(self.data_path.resolve()).as_posix()
        recipe_id = hashlib.md5(relative_path.encode("utf-8")).hexdigest()
        category = self._category_from_path(path)
        title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        name = self._clean_name(title_match.group(1) if title_match else path.stem)
        sections = self._split_sections(text)
        description = self._extract_description(text)
        ingredients = self._extract_ingredients(sections)
        steps = self._extract_steps(sections)
        difficulty = self._extract_difficulty(text)
        return RecipeRecord(
            id=recipe_id,
            name=name,
            category=category,
            difficulty=difficulty,
            source=str(path),
            description=description,
            ingredients=ingredients,
            steps=steps,
            sections=sections,
            raw_text=text,
        )

    def _category_from_path(self, path: Path) -> str:
        parts = set(path.parts)
        for key, label in CATEGORY_MAPPING.items():
            if key in parts:
                return label
        return "其他"

    def _can_connect_port(self) -> bool:
        match = re.match(r"bolt://([^:/]+):(\d+)", self.neo4j_uri)
        if not match:
            return False
        host, port = match.group(1), int(match.group(2))
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            return False

    def _split_sections(self, text: str) -> dict[str, str]:
        matches = list(re.finditer(r"^##\s+(.+)$", text, re.MULTILINE))
        sections: dict[str, str] = {}
        for index, match in enumerate(matches):
            title = match.group(1).strip()
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            sections[title] = text[start:end].strip()
        return sections

    def _extract_description(self, text: str) -> str:
        without_comments = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
        without_images = re.sub(r"!\[[^\]]*]\([^)]+\)", "", without_comments)
        parts = re.split(r"^##\s+", without_images, maxsplit=1, flags=re.MULTILINE)
        intro = re.sub(r"^#\s+.+$", "", parts[0], flags=re.MULTILINE).strip()
        lines = [line.strip() for line in intro.splitlines() if line.strip()]
        return lines[0][:240] if lines else ""

    def _extract_ingredients(self, sections: dict[str, str]) -> list[Ingredient]:
        ingredient_text = self._find_section(sections, ("原料", "工具", "必备"))
        if not ingredient_text:
            return []
        ingredients: list[Ingredient] = []
        for line in ingredient_text.splitlines():
            item = self._parse_bullet(line)
            if not item:
                continue
            name, amount = self._split_amount(item)
            ingredients.append(Ingredient(name=name, amount=amount))
        return ingredients

    def _extract_steps(self, sections: dict[str, str]) -> list[str]:
        step_text = self._find_section(sections, ("操作", "步骤", "做法"))
        if not step_text:
            return []
        steps = [self._parse_bullet(line) for line in step_text.splitlines()]
        return [step for step in steps if step]

    def _extract_difficulty(self, text: str) -> str:
        stars = len(re.findall(r"★|⭐|🌟", text))
        return {
            1: "非常简单",
            2: "简单",
            3: "中等",
            4: "困难",
            5: "非常困难",
        }.get(stars, "未知")

    def _find_section(self, sections: dict[str, str], keywords: tuple[str, ...]) -> str:
        for title, content in sections.items():
            if any(keyword in title for keyword in keywords):
                return content
        return ""

    def _parse_bullet(self, line: str) -> str | None:
        cleaned = re.sub(r"<!--.*?-->", "", line).strip()
        cleaned = re.sub(r"^[-*]\s+", "", cleaned)
        cleaned = re.sub(r"^\d+[.)、]\s*", "", cleaned)
        return cleaned.strip() or None

    def _split_amount(self, item: str) -> tuple[str, str | None]:
        match = re.match(r"(.+?)\s+([0-9./~-]+.*)$", item)
        if not match:
            return item[:80], None
        return match.group(1).strip()[:80], match.group(2).strip()[:120]

    def _clean_name(self, name: str) -> str:
        return re.sub(r"的做法$", "", name.strip())

    def _chunk(self, record: RecipeRecord, chunk_type: str, text: str) -> dict:
        chunk_id = hashlib.md5(f"{record.id}:{chunk_type}".encode("utf-8")).hexdigest()
        return {
            "id": f"{record.id}:{chunk_id}",
            "recipe_id": record.id,
            "chunk_id": chunk_id,
            "chunk_type": chunk_type,
            "recipe_name": record.name,
            "category": record.category,
            "difficulty": record.difficulty,
            "text": text,
            "metadata": {
                "source": record.source,
                "recipe_id": record.id,
                "recipe_name": record.name,
            },
        }

    def _ensure_constraints(self, session) -> None:
        session.run("CREATE CONSTRAINT recipe_id IF NOT EXISTS FOR (r:Recipe) REQUIRE r.id IS UNIQUE")
        session.run("CREATE CONSTRAINT ingredient_name IF NOT EXISTS FOR (i:Ingredient) REQUIRE i.name IS UNIQUE")
        session.run("CREATE CONSTRAINT category_name IF NOT EXISTS FOR (c:Category) REQUIRE c.name IS UNIQUE")

    @staticmethod
    def _write_recipe(tx, record: RecipeRecord) -> None:
        tx.run(
            """
            MERGE (r:Recipe {id: $id})
            SET r.name = $name, r.category = $category, r.difficulty = $difficulty,
                r.source = $source, r.description = $description
            MERGE (c:Category {name: $category})
            MERGE (r)-[:BELONGS_TO]->(c)
            """,
            id=record.id,
            name=record.name,
            category=record.category,
            difficulty=record.difficulty,
            source=record.source,
            description=record.description,
        )
        for item in record.ingredients:
            tx.run(
                """
                MATCH (r:Recipe {id: $recipe_id})
                MERGE (i:Ingredient {name: $name})
                MERGE (r)-[rel:HAS_INGREDIENT]->(i)
                SET rel.amount = $amount, rel.required = $required
                """,
                recipe_id=record.id,
                name=item.name,
                amount=item.amount,
                required=item.required,
            )
        for order, step in enumerate(record.steps, 1):
            step_id = hashlib.md5(f"{record.id}:{order}:{step}".encode("utf-8")).hexdigest()
            tx.run(
                """
                MATCH (r:Recipe {id: $recipe_id})
                MERGE (s:Step {id: $step_id})
                SET s.order = $order, s.text = $text
                MERGE (r)-[:HAS_STEP]->(s)
                """,
                recipe_id=record.id,
                step_id=step_id,
                order=order,
                text=step,
            )
