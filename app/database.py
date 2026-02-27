"""SQLite database layer for Recipe Pro."""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Generator, Optional

from .models import Ingredient, Recipe, RecipeIngredient, RecipeStep

logger = logging.getLogger(__name__)


class RecipeDatabase:
    """SQLite-backed storage for recipes and ingredients."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ingredients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    category TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS recipes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    instructions TEXT NOT NULL,
                    servings INTEGER,
                    prep_time INTEGER,
                    cook_time INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS recipe_ingredients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recipe_id INTEGER NOT NULL,
                    ingredient_id INTEGER NOT NULL,
                    quantity REAL NOT NULL,
                    unit TEXT NOT NULL,
                    notes TEXT,
                    FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE,
                    FOREIGN KEY (ingredient_id) REFERENCES ingredients(id),
                    UNIQUE(recipe_id, ingredient_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS recipe_steps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recipe_id INTEGER NOT NULL,
                    step_order INTEGER NOT NULL,
                    instruction TEXT NOT NULL,
                    FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE,
                    UNIQUE(recipe_id, step_order)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_recipe_ingredients_recipe_id
                ON recipe_ingredients(recipe_id)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_recipe_ingredients_ingredient_id
                ON recipe_ingredients(ingredient_id)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_recipe_steps_recipe_id
                ON recipe_steps(recipe_id)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_recipes_title
                ON recipes(title)
                """
            )
            conn.commit()

    @staticmethod
    def _normalize_ingredient_name(name: str) -> str:
        return name.strip().lower()

    @staticmethod
    def _parse_steps_from_instructions(instructions: str) -> list[str]:
        return [line.strip() for line in instructions.splitlines() if line.strip()]

    def _extract_steps(self, recipe_data: dict[str, Any]) -> list[str]:
        raw_steps = recipe_data.get("steps")
        if isinstance(raw_steps, list):
            steps = [str(step).strip() for step in raw_steps if str(step).strip()]
            if steps:
                return steps
        return self._parse_steps_from_instructions(str(recipe_data.get("instructions", "")))

    def get_or_create_ingredient(
        self,
        name: str,
        category: Optional[str],
        conn: Optional[sqlite3.Connection] = None,
    ) -> Ingredient:
        normalized_name = self._normalize_ingredient_name(name)
        if not normalized_name:
            raise ValueError("Ingredient name cannot be empty")

        category_clean = category.strip() if isinstance(category, str) and category.strip() else None

        if conn is not None:
            return self._get_or_create_ingredient_with_conn(conn, normalized_name, category_clean)

        with self._connect() as local_conn:
            ingredient = self._get_or_create_ingredient_with_conn(local_conn, normalized_name, category_clean)
            local_conn.commit()
            return ingredient

    def _get_or_create_ingredient_with_conn(
        self, conn: sqlite3.Connection, normalized_name: str, category: Optional[str]
    ) -> Ingredient:
        existing = conn.execute(
            "SELECT id, name, category FROM ingredients WHERE name = ?",
            (normalized_name,),
        ).fetchone()
        if existing:
            ingredient = Ingredient.from_row(dict(existing))
            if category and ingredient.category != category:
                conn.execute(
                    "UPDATE ingredients SET category = ? WHERE id = ?",
                    (category, ingredient.id),
                )
                ingredient.category = category
            return ingredient

        cursor = conn.execute(
            "INSERT INTO ingredients (name, category) VALUES (?, ?)",
            (normalized_name, category),
        )
        return Ingredient(id=cursor.lastrowid, name=normalized_name, category=category)

    def get_all_ingredients(self) -> list[Ingredient]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, name, category FROM ingredients ORDER BY name ASC"
            ).fetchall()
        return [Ingredient.from_row(dict(row)) for row in rows]

    def get_ingredient_by_id(self, ingredient_id: int) -> Optional[Ingredient]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, name, category FROM ingredients WHERE id = ?",
                (ingredient_id,),
            ).fetchone()
        return Ingredient.from_row(dict(row)) if row else None

    def get_recipes_by_ingredient(self, ingredient_id: int) -> list[Recipe]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT r.id, r.title, r.instructions, r.servings, r.prep_time, r.cook_time,
                       r.created_at, r.updated_at
                FROM recipes r
                INNER JOIN recipe_ingredients ri ON ri.recipe_id = r.id
                WHERE ri.ingredient_id = ?
                ORDER BY r.title ASC
                """,
                (ingredient_id,),
            ).fetchall()
        return [Recipe.from_row(dict(row)) for row in rows]

    def create_recipe(self, recipe_data: dict[str, Any]) -> Recipe:
        now = datetime.now(UTC).isoformat()
        ingredients_payload = recipe_data.get("ingredients", [])
        steps_payload = self._extract_steps(recipe_data)
        instructions_text = "\n".join(steps_payload)

        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO recipes (title, instructions, servings, prep_time, cook_time, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    recipe_data.get("title", ""),
                    instructions_text,
                    recipe_data.get("servings"),
                    recipe_data.get("prep_time"),
                    recipe_data.get("cook_time"),
                    now,
                    now,
                ),
            )
            recipe_id = cursor.lastrowid

            for item in ingredients_payload:
                ingredient = self.get_or_create_ingredient(
                    name=item.get("name", ""),
                    category=item.get("category"),
                    conn=conn,
                )
                conn.execute(
                    """
                    INSERT OR REPLACE INTO recipe_ingredients
                    (recipe_id, ingredient_id, quantity, unit, notes)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        recipe_id,
                        ingredient.id,
                        float(item.get("quantity") or 0.0),
                        item.get("unit", ""),
                        item.get("notes"),
                    ),
                )

            for index, instruction in enumerate(steps_payload, start=1):
                conn.execute(
                    """
                    INSERT INTO recipe_steps (recipe_id, step_order, instruction)
                    VALUES (?, ?, ?)
                    """,
                    (recipe_id, index, instruction),
                )
            conn.commit()

        recipe = self.get_recipe_by_id(recipe_id)
        if not recipe:
            raise RuntimeError("Failed to load created recipe")
        return recipe

    def get_all_recipes(self, search: Optional[str] = None) -> list[Recipe]:
        query = (
            "SELECT id, title, instructions, servings, prep_time, cook_time, created_at, updated_at "
            "FROM recipes"
        )
        params: tuple[Any, ...] = ()

        if search and search.strip():
            query += " WHERE title LIKE ?"
            params = (f"%{search.strip()}%",)

        query += " ORDER BY updated_at DESC"

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        recipes = [Recipe.from_row(dict(row)) for row in rows]
        for recipe in recipes:
            recipe.instructions = ""
        return recipes

    def _get_recipe_ingredients(self, conn: sqlite3.Connection, recipe_id: int) -> list[RecipeIngredient]:
        rows = conn.execute(
            """
            SELECT
                ri.id,
                ri.recipe_id,
                ri.ingredient_id,
                ri.quantity,
                ri.unit,
                ri.notes,
                i.name AS ingredient_name,
                i.category AS ingredient_category
            FROM recipe_ingredients ri
            INNER JOIN ingredients i ON i.id = ri.ingredient_id
            WHERE ri.recipe_id = ?
            ORDER BY i.name ASC
            """,
            (recipe_id,),
        ).fetchall()
        return [RecipeIngredient.from_row(dict(row)) for row in rows]

    def _get_recipe_steps(self, conn: sqlite3.Connection, recipe_id: int) -> list[RecipeStep]:
        rows = conn.execute(
            """
            SELECT id, recipe_id, step_order, instruction
            FROM recipe_steps
            WHERE recipe_id = ?
            ORDER BY step_order ASC
            """,
            (recipe_id,),
        ).fetchall()
        return [RecipeStep.from_row(dict(row)) for row in rows]

    def get_recipe_by_id(self, recipe_id: int) -> Optional[Recipe]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, title, instructions, servings, prep_time, cook_time, created_at, updated_at
                FROM recipes
                WHERE id = ?
                """,
                (recipe_id,),
            ).fetchone()
            if not row:
                return None

            recipe = Recipe.from_row(dict(row))
            recipe.ingredients = self._get_recipe_ingredients(conn, recipe_id)
            recipe.steps = self._get_recipe_steps(conn, recipe_id)
            if not recipe.steps:
                parsed = self._parse_steps_from_instructions(recipe.instructions)
                recipe.steps = [
                    RecipeStep(recipe_id=recipe.id, step_order=index, instruction=instruction)
                    for index, instruction in enumerate(parsed, start=1)
                ]
            return recipe

    def update_recipe(self, recipe_id: int, recipe_data: dict[str, Any]) -> Optional[Recipe]:
        now = datetime.now(UTC).isoformat()
        ingredients_payload = recipe_data.get("ingredients", [])
        steps_payload = self._extract_steps(recipe_data)
        instructions_text = "\n".join(steps_payload)

        with self._connect() as conn:
            existing = conn.execute("SELECT id FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
            if not existing:
                return None

            conn.execute(
                """
                UPDATE recipes
                SET title = ?, instructions = ?, servings = ?, prep_time = ?, cook_time = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    recipe_data.get("title", ""),
                    instructions_text,
                    recipe_data.get("servings"),
                    recipe_data.get("prep_time"),
                    recipe_data.get("cook_time"),
                    now,
                    recipe_id,
                ),
            )

            conn.execute("DELETE FROM recipe_ingredients WHERE recipe_id = ?", (recipe_id,))
            conn.execute("DELETE FROM recipe_steps WHERE recipe_id = ?", (recipe_id,))

            for item in ingredients_payload:
                ingredient = self.get_or_create_ingredient(
                    name=item.get("name", ""),
                    category=item.get("category"),
                    conn=conn,
                )
                conn.execute(
                    """
                    INSERT INTO recipe_ingredients
                    (recipe_id, ingredient_id, quantity, unit, notes)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        recipe_id,
                        ingredient.id,
                        float(item.get("quantity") or 0.0),
                        item.get("unit", ""),
                        item.get("notes"),
                    ),
                )

            for index, instruction in enumerate(steps_payload, start=1):
                conn.execute(
                    """
                    INSERT INTO recipe_steps (recipe_id, step_order, instruction)
                    VALUES (?, ?, ?)
                    """,
                    (recipe_id, index, instruction),
                )

            conn.commit()

        return self.get_recipe_by_id(recipe_id)

    def delete_recipe(self, recipe_id: int) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_shopping_list(self, recipe_ids: list[int]) -> dict[str, Any]:
        if not recipe_ids:
            return {"items": [], "by_category": {}}

        placeholders = ",".join("?" for _ in recipe_ids)

        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    ri.ingredient_id,
                    i.name,
                    i.category,
                    ri.quantity,
                    ri.unit,
                    r.title AS recipe_title
                FROM recipe_ingredients ri
                INNER JOIN ingredients i ON i.id = ri.ingredient_id
                INNER JOIN recipes r ON r.id = ri.recipe_id
                WHERE ri.recipe_id IN ({placeholders})
                ORDER BY i.name ASC
                """,
                tuple(recipe_ids),
            ).fetchall()

        grouped: dict[tuple[int, str], dict[str, Any]] = {}
        for row in rows:
            key = (row["ingredient_id"], row["unit"])
            if key not in grouped:
                grouped[key] = {
                    "ingredient_id": row["ingredient_id"],
                    "name": row["name"],
                    "category": row["category"] or "other",
                    "total_quantity": 0.0,
                    "unit": row["unit"],
                    "recipes": set(),
                }
            grouped[key]["total_quantity"] += float(row["quantity"] or 0.0)
            grouped[key]["recipes"].add(row["recipe_title"])

        items = []
        for value in grouped.values():
            items.append(
                {
                    "ingredient_id": value["ingredient_id"],
                    "name": value["name"],
                    "category": value["category"],
                    "total_quantity": value["total_quantity"],
                    "unit": value["unit"],
                    "recipes": sorted(value["recipes"]),
                }
            )

        items.sort(key=lambda item: (item["category"], item["name"], item["unit"]))

        by_category: dict[str, list[dict[str, Any]]] = {}
        for item in items:
            by_category.setdefault(item["category"], []).append(item)

        return {"items": items, "by_category": by_category}

    def get_recipe_suggestions(self, ingredient_ids: list[int]) -> list[dict[str, Any]]:
        recipe_rows = self.get_all_recipes()
        selected = set(ingredient_ids)

        suggestions: list[dict[str, Any]] = []
        for recipe in recipe_rows:
            full_recipe = self.get_recipe_by_id(recipe.id or 0)
            if not full_recipe:
                continue

            ingredient_entries = full_recipe.ingredients
            total_ingredients = len(ingredient_entries)
            if total_ingredients == 0:
                continue

            matched = [
                item for item in ingredient_entries if item.ingredient_id in selected
            ]
            missing = [
                item for item in ingredient_entries if item.ingredient_id not in selected
            ]

            match_count = len(matched)
            match_percentage = int(round((match_count / total_ingredients) * 100))

            if ingredient_ids and match_count == 0:
                continue

            suggestions.append(
                {
                    "recipe": {
                        "id": full_recipe.id,
                        "title": full_recipe.title,
                        "servings": full_recipe.servings,
                        "prep_time": full_recipe.prep_time,
                        "cook_time": full_recipe.cook_time,
                    },
                    "match_count": match_count,
                    "total_ingredients": total_ingredients,
                    "match_percentage": match_percentage,
                    "matched_ingredients": [
                        item.ingredient.name
                        for item in matched
                        if item.ingredient is not None
                    ],
                    "missing_ingredients": [
                        item.ingredient.name
                        for item in missing
                        if item.ingredient is not None
                    ],
                }
            )

        suggestions.sort(
            key=lambda item: (
                item["match_percentage"],
                item["match_count"],
                item["recipe"]["title"],
            ),
            reverse=True,
        )
        return suggestions

    def get_stats(self) -> dict[str, Any]:
        with self._connect() as conn:
            recipe_count = conn.execute("SELECT COUNT(*) AS count FROM recipes").fetchone()["count"]
            ingredient_count = conn.execute("SELECT COUNT(*) AS count FROM ingredients").fetchone()["count"]
            category_rows = conn.execute(
                """
                SELECT COALESCE(category, 'other') AS category, COUNT(*) AS count
                FROM ingredients
                GROUP BY COALESCE(category, 'other')
                ORDER BY category ASC
                """
            ).fetchall()

        return {
            "recipe_count": recipe_count,
            "ingredient_count": ingredient_count,
            "category_counts": {row["category"]: row["count"] for row in category_rows},
        }
