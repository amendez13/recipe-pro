"""FastAPI app for Recipe Pro."""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator

from .config import Config, get_default_config_path, load_config
from .database import RecipeDatabase

logger = logging.getLogger(__name__)

MODULE_DIR = Path(__file__).resolve().parent
STATIC_DIR = MODULE_DIR / "static"
TEMPLATES_DIR = MODULE_DIR / "templates"
INDEX_FILE = TEMPLATES_DIR / "index.html"


class IngredientInput(BaseModel):
    name: str = Field(min_length=1)
    quantity: float = Field(ge=0)
    unit: str = Field(min_length=1)
    category: Optional[str] = None
    notes: Optional[str] = None


class IngredientPreferencePayload(BaseModel):
    default_available: bool


class RecipePayload(BaseModel):
    title: str = Field(min_length=1)
    instructions: str = ""
    steps: list[str] = Field(default_factory=list)
    servings: Optional[int] = Field(default=None, ge=1)
    prep_time: Optional[int] = Field(default=None, ge=0)
    cook_time: Optional[int] = Field(default=None, ge=0)
    ingredients: list[IngredientInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_instructions_or_steps(self) -> "RecipePayload":
        normalized_steps = [step.strip() for step in self.steps if isinstance(step, str) and step.strip()]
        if normalized_steps:
            self.steps = normalized_steps
            return self
        if self.instructions.strip():
            return self
        raise ValueError("Provide recipe steps or instructions")


class RecipeIdsPayload(BaseModel):
    recipe_ids: list[int] = Field(default_factory=list)


class SuggestionPayload(BaseModel):
    ingredient_ids: list[int] = Field(default_factory=list)


class RecipeImportPayload(BaseModel):
    url: str = Field(min_length=1)


def _extract_json_from_text(text: str) -> dict[str, Any]:
    raw = text.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        if len(lines) >= 3:
            raw = "\n".join(lines[1:-1]).strip()
    return json.loads(raw)


def _normalize_import_recipe(data: dict[str, Any]) -> dict[str, Any]:
    steps = [str(step).strip() for step in data.get("steps", []) if str(step).strip()]
    ingredients = []
    for item in data.get("ingredients", []):
        name = str(item.get("name", "")).strip()
        unit = str(item.get("unit", "")).strip()
        if not name or not unit:
            continue
        ingredients.append(
            {
                "name": name,
                "quantity": float(item.get("quantity") or 0),
                "unit": unit,
                "category": str(item.get("category") or "").strip() or None,
                "notes": str(item.get("notes") or "").strip() or None,
            }
        )

    return {
        "title": str(data.get("title", "")).strip(),
        "steps": steps,
        "instructions": "\n".join(steps),
        "servings": data.get("servings"),
        "prep_time": data.get("prep_time"),
        "cook_time": data.get("cook_time"),
        "ingredients": ingredients,
        "source_url": str(data.get("source_url", "")).strip() or None,
    }


def create_app(config: Config | None = None) -> FastAPI:
    app = FastAPI(
        title="Recipe Pro",
        description="Recipe management optimized for cooking mode",
        version="1.0.0",
    )

    cfg = config
    if cfg is None:
        cfg = load_config(get_default_config_path())
    app.state.config = cfg

    db = RecipeDatabase(cfg.database.path)
    app.state.db = db

    logger.info("Starting Recipe Pro with database at %s", cfg.database.path)

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    async def serve_index() -> FileResponse:
        return FileResponse(INDEX_FILE)

    @app.get("/api/recipes")
    async def list_recipes(search: Optional[str] = None) -> list[dict[str, Any]]:
        recipes = app.state.db.get_all_recipes(search=search)
        return [
            {
                "id": recipe.id,
                "title": recipe.title,
                "servings": recipe.servings,
                "prep_time": recipe.prep_time,
                "cook_time": recipe.cook_time,
                "created_at": recipe.created_at.isoformat() if recipe.created_at else None,
            }
            for recipe in recipes
        ]

    @app.post("/api/recipes", status_code=201)
    async def create_recipe(data: RecipePayload) -> dict[str, Any]:
        created = app.state.db.create_recipe(data.model_dump())
        return created.to_dict()

    @app.get("/api/recipes/{recipe_id}")
    async def get_recipe(recipe_id: int) -> dict[str, Any]:
        recipe = app.state.db.get_recipe_by_id(recipe_id)
        if not recipe:
            raise HTTPException(status_code=404, detail="Recipe not found")
        return recipe.to_dict()

    @app.put("/api/recipes/{recipe_id}")
    async def update_recipe(recipe_id: int, data: RecipePayload) -> dict[str, Any]:
        updated = app.state.db.update_recipe(recipe_id, data.model_dump())
        if not updated:
            raise HTTPException(status_code=404, detail="Recipe not found")
        return updated.to_dict()

    @app.delete("/api/recipes/{recipe_id}")
    async def delete_recipe(recipe_id: int) -> dict[str, bool]:
        deleted = app.state.db.delete_recipe(recipe_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Recipe not found")
        return {"success": True}

    @app.get("/api/ingredients")
    async def list_ingredients() -> list[dict[str, Any]]:
        ingredients = app.state.db.get_all_ingredients()
        return [ingredient.to_dict() for ingredient in ingredients]

    @app.get("/api/ingredients/{ingredient_id}/recipes")
    async def recipes_by_ingredient(ingredient_id: int) -> list[dict[str, Any]]:
        ingredient = app.state.db.get_ingredient_by_id(ingredient_id)
        if ingredient is None:
            raise HTTPException(status_code=404, detail="Ingredient not found")
        recipes = app.state.db.get_recipes_by_ingredient(ingredient_id)
        return [
            {
                "id": recipe.id,
                "title": recipe.title,
                "servings": recipe.servings,
                "prep_time": recipe.prep_time,
                "cook_time": recipe.cook_time,
            }
            for recipe in recipes
        ]

    @app.patch("/api/ingredients/{ingredient_id}")
    async def update_ingredient_preference(
        ingredient_id: int, data: IngredientPreferencePayload
    ) -> dict[str, Any]:
        updated = app.state.db.update_ingredient_default_available(
            ingredient_id=ingredient_id,
            default_available=data.default_available,
        )
        if updated is None:
            raise HTTPException(status_code=404, detail="Ingredient not found")
        return updated.to_dict()

    @app.post("/api/ingredients/{ingredient_id}")
    async def update_ingredient_preference_post(
        ingredient_id: int, data: IngredientPreferencePayload
    ) -> dict[str, Any]:
        updated = app.state.db.update_ingredient_default_available(
            ingredient_id=ingredient_id,
            default_available=data.default_available,
        )
        if updated is None:
            raise HTTPException(status_code=404, detail="Ingredient not found")
        return updated.to_dict()

    @app.post("/api/ingredients/{ingredient_id}/default")
    async def update_ingredient_default(
        ingredient_id: int, data: IngredientPreferencePayload
    ) -> dict[str, Any]:
        updated = app.state.db.update_ingredient_default_available(
            ingredient_id=ingredient_id,
            default_available=data.default_available,
        )
        if updated is None:
            raise HTTPException(status_code=404, detail="Ingredient not found")
        return updated.to_dict()

    @app.get("/api/stats")
    async def get_stats() -> dict[str, Any]:
        return app.state.db.get_stats()

    @app.post("/api/shopping-list")
    async def get_shopping_list(data: RecipeIdsPayload) -> dict[str, Any]:
        return app.state.db.get_shopping_list(data.recipe_ids)

    @app.post("/api/suggestions")
    async def get_suggestions(data: SuggestionPayload) -> dict[str, Any]:
        suggestions = app.state.db.get_recipe_suggestions(data.ingredient_ids)
        return {"suggestions": suggestions}

    @app.post("/api/recipes/import-preview")
    async def get_recipe_import_preview(data: RecipeImportPayload) -> dict[str, Any]:
        parsed = urlparse(data.url.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise HTTPException(status_code=400, detail="Invalid URL")

        prompt = (
            "Extract the recipe from this URL and return only valid JSON with keys: "
            "title, source_url, servings, prep_time, cook_time, steps (array of strings), "
            "ingredients (array of objects with name, quantity, unit, category, notes). "
            f"URL: {data.url.strip()}"
        )
        try:
            result = subprocess.run(
                ["claude", "-p", prompt],
                capture_output=True,
                text=True,
                check=True,
                timeout=120,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=500, detail="claude CLI not found on server") from exc
        except subprocess.TimeoutExpired as exc:
            raise HTTPException(status_code=504, detail="Recipe import timed out") from exc
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            raise HTTPException(status_code=502, detail=f"Recipe import failed: {stderr or 'claude CLI error'}") from exc

        try:
            parsed_json = _extract_json_from_text(result.stdout)
            normalized = _normalize_import_recipe(parsed_json)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=502, detail="Recipe import returned invalid JSON") from exc

        if not normalized["title"] or not normalized["steps"] or not normalized["ingredients"]:
            raise HTTPException(status_code=422, detail="Imported recipe is incomplete")
        return normalized

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        return {"status": "healthy"}

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str) -> FileResponse:
        if full_path.startswith("api/") or full_path.startswith("static/"):
            raise HTTPException(status_code=404, detail="Not found")
        return FileResponse(INDEX_FILE)

    return app


app = create_app()
