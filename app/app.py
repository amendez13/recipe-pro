"""FastAPI app for Recipe Pro."""

from __future__ import annotations

import json
import logging
import re
import subprocess
from html import unescape
from pathlib import Path
from typing import Any, Optional
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request as UrlRequest, urlopen

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator

from .auth import create_session_token, decode_session_token, verify_credentials
from .config import Config, get_default_config_path, load_config
from .database import RecipeDatabase

logger = logging.getLogger(__name__)

MODULE_DIR = Path(__file__).resolve().parent
STATIC_DIR = MODULE_DIR / "static"
TEMPLATES_DIR = MODULE_DIR / "templates"
INDEX_FILE = TEMPLATES_DIR / "index.html"

RECIPE_IMPORT_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "source_url": {"type": ["string", "null"]},
        "servings": {"type": ["integer", "null"]},
        "prep_time": {"type": ["integer", "null"]},
        "cook_time": {"type": ["integer", "null"]},
        "steps": {"type": "array", "items": {"type": "string"}},
        "ingredients": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "quantity": {"type": ["number", "null"]},
                    "unit": {"type": ["string", "null"]},
                    "category": {"type": ["string", "null"]},
                    "notes": {"type": ["string", "null"]},
                },
                "required": ["name", "quantity", "unit", "category", "notes"],
            },
        },
    },
    "required": ["title", "source_url", "servings", "prep_time", "cook_time", "steps", "ingredients"],
}


class IngredientInput(BaseModel):
    name: str = Field(min_length=1)
    quantity: float = Field(ge=0)
    unit: str = Field(min_length=1)
    category: Optional[str] = None
    notes: Optional[str] = None


class IngredientPreferencePayload(BaseModel):
    default_available: bool


class IngredientMergePayload(BaseModel):
    primary_id: int = Field(gt=0)
    secondary_id: int = Field(gt=0)
    confirm_collision_drop: bool = False


class IngredientMergePreviewPayload(BaseModel):
    primary_id: int = Field(gt=0)
    secondary_id: int = Field(gt=0)


class RecipePayload(BaseModel):
    title: str = Field(min_length=1)
    instructions: str = ""
    url: Optional[str] = None
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
    url: Optional[str] = None
    text: Optional[str] = None

    @model_validator(mode="after")
    def validate_input(self) -> "RecipeImportPayload":
        has_url = bool((self.url or "").strip())
        has_text = bool((self.text or "").strip())
        if has_url == has_text:
            raise ValueError("Provide exactly one import input: url or text")
        return self


class LoginPayload(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    remember: bool = True


def _parse_fractional_number(value: str) -> Optional[float]:
    token = value.strip()
    if not token:
        return None
    if " " in token:
        parts = token.split()
        if len(parts) == 2 and "/" in parts[1]:
            whole = float(parts[0])
            num, den = parts[1].split("/", 1)
            return whole + (float(num) / float(den))
    if "/" in token:
        num, den = token.split("/", 1)
        return float(num) / float(den)
    return float(token)


def _parse_duration_minutes(value: Any) -> Optional[int]:
    if value is None:
        return None
    raw = str(value).strip().upper()
    if not raw:
        return None
    if raw.isdigit():
        return int(raw)
    match = re.fullmatch(r"P(?:\d+D)?(?:T(?:(\d+)H)?(?:(\d+)M)?)?", raw)
    if not match:
        return None
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    total = (hours * 60) + minutes
    return total if total > 0 else None


def _extract_first_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    match = re.search(r"\d+", str(value))
    return int(match.group(0)) if match else None


def _extract_steps(recipe_node: dict[str, Any]) -> list[str]:
    raw = recipe_node.get("recipeInstructions") or recipe_node.get("instructions")
    if raw is None:
        return []

    def _normalize_step(step: Any) -> Optional[str]:
        if isinstance(step, str):
            text = step.strip()
            return text or None
        if isinstance(step, dict):
            text = str(step.get("text") or step.get("name") or "").strip()
            return text or None
        return None

    steps: list[str] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict) and "itemListElement" in item:
                nested = item.get("itemListElement") or []
                if isinstance(nested, list):
                    for nested_item in nested:
                        normalized = _normalize_step(nested_item)
                        if normalized:
                            steps.append(normalized)
                continue
            normalized = _normalize_step(item)
            if normalized:
                steps.append(normalized)
    else:
        normalized = _normalize_step(raw)
        if normalized:
            split_steps = [s.strip() for s in re.split(r"\n+|\r+|\.\s+(?=[A-Z])", normalized) if s.strip()]
            steps.extend(split_steps if len(split_steps) > 1 else [normalized])
    return steps


def _parse_ingredient_line(text: str) -> dict[str, Any]:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return {}

    pattern = re.compile(
        r"^(?:(?P<qty>\d+(?:\.\d+)?(?:/\d+)?(?:\s+\d+/\d+)?)\s+)?(?:(?P<unit>[A-Za-z]+)\s+)?(?P<name>.+)$"
    )
    match = pattern.match(cleaned)
    if not match:
        return {"name": cleaned, "quantity": 1.0, "unit": "nonunit", "category": None, "notes": None}

    qty_token = match.group("qty") or "1"
    unit_token = (match.group("unit") or "").strip().lower()
    name_token = (match.group("name") or "").strip(" ,.;:")

    try:
        quantity = _parse_fractional_number(qty_token) or 1.0
    except ValueError:
        quantity = 1.0
    if quantity < 0:
        quantity = 1.0
    unit = unit_token or "nonunit"
    return {"name": name_token or cleaned, "quantity": quantity, "unit": unit, "category": None, "notes": None}


def _find_recipe_node(candidate: Any) -> Optional[dict[str, Any]]:
    if isinstance(candidate, dict):
        type_value = candidate.get("@type")
        if isinstance(type_value, list):
            type_names = {str(item).lower() for item in type_value}
        else:
            type_names = {str(type_value).lower()} if type_value else set()
        if "recipe" in type_names and candidate.get("name"):
            return candidate
        if "@graph" in candidate:
            graph = candidate.get("@graph")
            if isinstance(graph, list):
                for item in graph:
                    found = _find_recipe_node(item)
                    if found:
                        return found
        for value in candidate.values():
            found = _find_recipe_node(value)
            if found:
                return found
    elif isinstance(candidate, list):
        for item in candidate:
            found = _find_recipe_node(item)
            if found:
                return found
    return None


def _extract_recipe_from_url(url: str) -> Optional[dict[str, Any]]:
    request = UrlRequest(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; RecipePro/1.0; +https://example.local)",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    try:
        with urlopen(request, timeout=25) as response:
            body = response.read().decode("utf-8", errors="ignore")
    except (URLError, TimeoutError, ValueError):
        return None

    json_ld_blocks = re.findall(
        r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
        body,
        flags=re.IGNORECASE | re.DOTALL,
    )
    for block in json_ld_blocks:
        raw = unescape(block).strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue

        recipe_node = _find_recipe_node(payload)
        if not recipe_node:
            continue

        title = str(recipe_node.get("name") or "").strip()
        ingredients_raw = recipe_node.get("recipeIngredient") or recipe_node.get("ingredients") or []
        if isinstance(ingredients_raw, str):
            ingredients_raw = [ingredients_raw]
        ingredients = []
        for entry in ingredients_raw:
            if isinstance(entry, str):
                parsed_line = _parse_ingredient_line(entry)
                if parsed_line.get("name"):
                    ingredients.append(parsed_line)
            elif isinstance(entry, dict):
                parsed_line = _parse_ingredient_line(str(entry.get("text") or entry.get("name") or ""))
                if parsed_line.get("name"):
                    ingredients.append(parsed_line)

        steps = _extract_steps(recipe_node)
        if not title or not steps or not ingredients:
            continue

        return {
            "title": title,
            "steps": steps,
            "instructions": "\n".join(steps),
            "servings": _extract_first_int(recipe_node.get("recipeYield")),
            "prep_time": _parse_duration_minutes(recipe_node.get("prepTime")),
            "cook_time": _parse_duration_minutes(recipe_node.get("cookTime")),
            "ingredients": ingredients,
            "source_url": url,
        }

    return None


def _extract_json_from_text(text: str) -> dict[str, Any]:
    raw = text.strip()
    if not raw:
        raise ValueError("Empty import response")

    # Fast-path for already clean JSON output.
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # Common case: fenced JSON block.
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, flags=re.IGNORECASE | re.DOTALL)
    if fence_match:
        parsed = json.loads(fence_match.group(1))
        if isinstance(parsed, dict):
            return parsed

    # Fallback: find the first balanced {...} object in mixed prose.
    start = raw.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escaped = False
        for idx in range(start, len(raw)):
            char = raw[idx]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    candidate = raw[start : idx + 1]
                    parsed = json.loads(candidate)
                    if isinstance(parsed, dict):
                        return parsed
                    break
        start = raw.find("{", start + 1)

    raise ValueError("No JSON object found in import response")


def _normalize_import_recipe(data: dict[str, Any]) -> dict[str, Any]:
    steps = [str(step).strip() for step in data.get("steps", []) if str(step).strip()]
    ingredients = []
    for item in data.get("ingredients", []):
        name = str(item.get("name") or "").strip()
        unit = str(item.get("unit") or "").strip() or "nonunit"
        if not name:
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
        "title": str(data.get("title") or "").strip(),
        "steps": steps,
        "instructions": "\n".join(steps),
        "servings": data.get("servings"),
        "prep_time": data.get("prep_time"),
        "cook_time": data.get("cook_time"),
        "ingredients": ingredients,
        "source_url": str(data.get("source_url") or "").strip() or None,
    }


def _run_claude_recipe_import(prompt: str, allow_web_fetch: bool = False) -> dict[str, Any]:
    command = [
        "claude",
        "-p",
        prompt,
        "--output-format",
        "json",
        "--json-schema",
        json.dumps(RECIPE_IMPORT_JSON_SCHEMA),
    ]
    if allow_web_fetch:
        command.extend(["--allowedTools", "WebFetch"])
    try:
        result = subprocess.run(
            command,
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
        wrapper = json.loads(result.stdout)
    except json.JSONDecodeError:
        wrapper = None

    try:
        model_output = result.stdout
        if isinstance(wrapper, dict) and wrapper.get("type") == "result":
            if wrapper.get("is_error"):
                errors = wrapper.get("errors") or []
                error_message = str(errors[0]).strip() if errors else str(wrapper.get("result") or "").strip()
                raise HTTPException(status_code=502, detail=error_message or "Recipe import failed during execution")
            structured_output = wrapper.get("structured_output")
            if isinstance(structured_output, dict):
                parsed_json = structured_output
            else:
                model_output = str(wrapper.get("result") or "")
                parsed_json = _extract_json_from_text(model_output)
        else:
            parsed_json = _extract_json_from_text(model_output)
        normalized = _normalize_import_recipe(parsed_json)
    except HTTPException:
        raise
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="Recipe import returned invalid JSON") from exc

    if not normalized["title"] or not normalized["steps"] or not normalized["ingredients"]:
        raise HTTPException(status_code=422, detail="Imported recipe is incomplete")
    return normalized


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

    user_map = {user.username: user for user in cfg.auth.users}
    app.state.user_map = user_map
    app.state.user_dbs = {}

    logger.info("Starting Recipe Pro with %d configured users", len(user_map))

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    def _resolve_session_user(request: Request):
        cookie_name = cfg.auth.session_cookie_name
        token = request.cookies.get(cookie_name)
        if not token:
            return None
        payload = decode_session_token(token, cfg.auth.session_secret)
        if not payload:
            return None
        username = payload.get("u")
        if not isinstance(username, str):
            return None
        for user in cfg.auth.users:
            if user.username == username:
                return user
        return None

    def _require_user(request: Request):
        user = _resolve_session_user(request)
        if user is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        return user

    def _db_for_user(username: str) -> RecipeDatabase:
        existing = app.state.user_dbs.get(username)
        if existing is not None:
            return existing
        user = app.state.user_map.get(username)
        if user is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        db_instance = RecipeDatabase(user.db_path)
        app.state.user_dbs[username] = db_instance
        return db_instance

    @app.get("/")
    async def serve_index() -> FileResponse:
        return FileResponse(INDEX_FILE)

    @app.post("/api/auth/login")
    async def auth_login(data: LoginPayload, response: Response) -> dict[str, str]:
        user = verify_credentials(data.username, data.password, cfg.auth.users)
        if user is None:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        ttl_seconds = cfg.auth.session_max_age_seconds if data.remember else min(
            cfg.auth.session_max_age_seconds, 60 * 60 * 12
        )
        token = create_session_token(user.username, cfg.auth.session_secret, ttl_seconds)
        response.set_cookie(
            key=cfg.auth.session_cookie_name,
            value=token,
            max_age=ttl_seconds,
            httponly=True,
            samesite="lax",
            secure=cfg.auth.session_secure,
            path="/",
        )
        return {"username": user.username}

    @app.post("/api/auth/logout")
    async def auth_logout(response: Response) -> dict[str, bool]:
        response.delete_cookie(
            key=cfg.auth.session_cookie_name,
            path="/",
            samesite="lax",
        )
        return {"success": True}

    @app.get("/api/auth/me")
    async def auth_me(request: Request) -> dict[str, str]:
        user = _resolve_session_user(request)
        if user is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        return {"username": user.username}

    @app.get("/api/recipes")
    async def list_recipes(request: Request, search: Optional[str] = None) -> list[dict[str, Any]]:
        user = _require_user(request)
        db = _db_for_user(user.username)
        recipes = db.get_all_recipes(search=search)
        return [
            {
                "id": recipe.id,
                "title": recipe.title,
                "url": recipe.url,
                "servings": recipe.servings,
                "prep_time": recipe.prep_time,
                "cook_time": recipe.cook_time,
                "created_at": recipe.created_at.isoformat() if recipe.created_at else None,
            }
            for recipe in recipes
        ]

    @app.post("/api/recipes", status_code=201)
    async def create_recipe(request: Request, data: RecipePayload) -> dict[str, Any]:
        user = _require_user(request)
        db = _db_for_user(user.username)
        created = db.create_recipe(data.model_dump())
        return created.to_dict()

    @app.get("/api/recipes/{recipe_id}")
    async def get_recipe(request: Request, recipe_id: int) -> dict[str, Any]:
        user = _require_user(request)
        db = _db_for_user(user.username)
        recipe = db.get_recipe_by_id(recipe_id)
        if not recipe:
            raise HTTPException(status_code=404, detail="Recipe not found")
        return recipe.to_dict()

    @app.put("/api/recipes/{recipe_id}")
    async def update_recipe(request: Request, recipe_id: int, data: RecipePayload) -> dict[str, Any]:
        user = _require_user(request)
        db = _db_for_user(user.username)
        updated = db.update_recipe(recipe_id, data.model_dump())
        if not updated:
            raise HTTPException(status_code=404, detail="Recipe not found")
        return updated.to_dict()

    @app.delete("/api/recipes/{recipe_id}")
    async def delete_recipe(request: Request, recipe_id: int) -> dict[str, bool]:
        user = _require_user(request)
        db = _db_for_user(user.username)
        deleted = db.delete_recipe(recipe_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Recipe not found")
        return {"success": True}

    @app.get("/api/ingredients")
    async def list_ingredients(request: Request) -> list[dict[str, Any]]:
        user = _require_user(request)
        db = _db_for_user(user.username)
        ingredients = db.get_all_ingredients()
        return [ingredient.to_dict() for ingredient in ingredients]

    @app.get("/api/ingredients/{ingredient_id}/recipes")
    async def recipes_by_ingredient(request: Request, ingredient_id: int) -> list[dict[str, Any]]:
        user = _require_user(request)
        db = _db_for_user(user.username)
        ingredient = db.get_ingredient_by_id(ingredient_id)
        if ingredient is None:
            raise HTTPException(status_code=404, detail="Ingredient not found")
        recipes = db.get_recipes_by_ingredient(ingredient_id)
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
        request: Request, ingredient_id: int, data: IngredientPreferencePayload
    ) -> dict[str, Any]:
        user = _require_user(request)
        db = _db_for_user(user.username)
        updated = db.update_ingredient_default_available(
            ingredient_id=ingredient_id,
            default_available=data.default_available,
        )
        if updated is None:
            raise HTTPException(status_code=404, detail="Ingredient not found")
        return updated.to_dict()

    @app.post("/api/ingredients/{ingredient_id:int}")
    async def update_ingredient_preference_post(
        request: Request, ingredient_id: int, data: IngredientPreferencePayload
    ) -> dict[str, Any]:
        user = _require_user(request)
        db = _db_for_user(user.username)
        updated = db.update_ingredient_default_available(
            ingredient_id=ingredient_id,
            default_available=data.default_available,
        )
        if updated is None:
            raise HTTPException(status_code=404, detail="Ingredient not found")
        return updated.to_dict()

    @app.post("/api/ingredients/{ingredient_id}/default")
    async def update_ingredient_default(
        request: Request, ingredient_id: int, data: IngredientPreferencePayload
    ) -> dict[str, Any]:
        user = _require_user(request)
        db = _db_for_user(user.username)
        updated = db.update_ingredient_default_available(
            ingredient_id=ingredient_id,
            default_available=data.default_available,
        )
        if updated is None:
            raise HTTPException(status_code=404, detail="Ingredient not found")
        return updated.to_dict()

    @app.post("/api/ingredients/merge-preview")
    async def ingredient_merge_preview(
        request: Request,
        data: IngredientMergePreviewPayload,
    ) -> dict[str, Any]:
        user = _require_user(request)
        db = _db_for_user(user.username)
        try:
            return db.get_ingredient_merge_preview(data.primary_id, data.secondary_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/ingredients/merge")
    async def ingredient_merge(
        request: Request,
        data: IngredientMergePayload,
    ) -> dict[str, Any]:
        user = _require_user(request)
        db = _db_for_user(user.username)
        try:
            return db.merge_ingredients(
                primary_id=data.primary_id,
                secondary_id=data.secondary_id,
                confirm_collision_drop=data.confirm_collision_drop,
            )
        except RuntimeError as exc:
            if "confirmation required" in str(exc).lower():
                raise HTTPException(
                    status_code=409,
                    detail="Collision confirmation required",
                ) from exc
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/ingredients/merge/{merge_event_id}/undo")
    async def ingredient_merge_undo(
        request: Request,
        merge_event_id: int,
    ) -> dict[str, Any]:
        user = _require_user(request)
        db = _db_for_user(user.username)
        try:
            return db.undo_ingredient_merge(merge_event_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/ingredients/merge-history")
    async def ingredient_merge_history(request: Request) -> list[dict[str, Any]]:
        user = _require_user(request)
        db = _db_for_user(user.username)
        return db.list_ingredient_merge_history(limit=50)

    @app.get("/api/stats")
    async def get_stats(request: Request) -> dict[str, Any]:
        user = _require_user(request)
        db = _db_for_user(user.username)
        return db.get_stats()

    @app.post("/api/shopping-list")
    async def get_shopping_list(request: Request, data: RecipeIdsPayload) -> dict[str, Any]:
        user = _require_user(request)
        db = _db_for_user(user.username)
        return db.get_shopping_list(data.recipe_ids)

    @app.post("/api/suggestions")
    async def get_suggestions(request: Request, data: SuggestionPayload) -> dict[str, Any]:
        user = _require_user(request)
        db = _db_for_user(user.username)
        suggestions = db.get_recipe_suggestions(data.ingredient_ids)
        return {"suggestions": suggestions}

    @app.post("/api/recipes/import-preview")
    async def get_recipe_import_preview(request: Request, data: RecipeImportPayload) -> dict[str, Any]:
        _require_user(request)
        if data.url:
            source_url = data.url.strip()
            parsed = urlparse(source_url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise HTTPException(status_code=400, detail="Invalid URL")

            extracted = _extract_recipe_from_url(source_url)
            if extracted:
                return extracted

            prompt = (
                "Extract the recipe from this URL and return only valid JSON with keys: "
                "title, source_url, servings, prep_time, cook_time, steps (array of strings), "
                "ingredients (array of objects with name, quantity, unit, category, notes). "
                f"URL: {source_url}"
            )
            return _run_claude_recipe_import(prompt, allow_web_fetch=True)

        source_text = (data.text or "").strip()
        if len(source_text) > 30000:
            raise HTTPException(status_code=400, detail="Recipe text is too long (max 30000 characters)")

        prompt = (
            "Extract the recipe from this raw recipe text and return only valid JSON with keys: "
            "title, source_url, servings, prep_time, cook_time, steps (array of strings), "
            "ingredients (array of objects with name, quantity, unit, category, notes). "
            "If source_url is unknown, use null.\n"
            "RECIPE TEXT:\n"
            f"{source_text}"
        )
        return _run_claude_recipe_import(prompt, allow_web_fetch=False)

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
