"""FastAPI app for Idea Canvas."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import Config, get_default_config_path, load_config
from .database import IdeaDatabase
from .models import Idea

logger = logging.getLogger(__name__)

MODULE_DIR = Path(__file__).resolve().parent
STATIC_DIR = MODULE_DIR / "static"
TEMPLATES_DIR = MODULE_DIR / "templates"
INDEX_FILE = TEMPLATES_DIR / "index.html"


class IdeaCreate(BaseModel):
    title: str
    content: str
    category: str = "general"
    tags: list[str] = []


class IdeaUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[list[str]] = None


def create_app(config: Config | None = None) -> FastAPI:
    app = FastAPI(
        title="Idea Canvas",
        description="A web app for capturing and organizing ideas",
        version="0.1.0",
    )

    cfg = config
    if cfg is None:
        cfg = load_config(get_default_config_path())
    app.state.config = cfg

    db = IdeaDatabase(cfg.database.path)
    app.state.db = db

    logger.info("Starting Idea Canvas with database at %s", cfg.database.path)

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    async def serve_index() -> FileResponse:
        return FileResponse(INDEX_FILE)

    @app.get("/api/ideas")
    async def list_ideas(
        category: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        ideas = app.state.db.list_all(category=category, limit=limit, offset=offset)
        total = app.state.db.count(category=category)
        return {
            "ideas": [idea.to_dict() for idea in ideas],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    @app.post("/api/ideas")
    async def create_idea(data: IdeaCreate) -> dict[str, Any]:
        idea = Idea(
            title=data.title,
            content=data.content,
            category=data.category,
            tags=data.tags,
        )
        created = app.state.db.create(idea)
        return created.to_dict()

    @app.get("/api/ideas/{idea_id}")
    async def get_idea(idea_id: int) -> dict[str, Any]:
        idea = app.state.db.get(idea_id)
        if not idea:
            raise HTTPException(status_code=404, detail="Idea not found")
        return idea.to_dict()

    @app.put("/api/ideas/{idea_id}")
    async def update_idea(idea_id: int, data: IdeaUpdate) -> dict[str, Any]:
        existing = app.state.db.get(idea_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Idea not found")

        if data.title is not None:
            existing.title = data.title
        if data.content is not None:
            existing.content = data.content
        if data.category is not None:
            existing.category = data.category
        if data.tags is not None:
            existing.tags = data.tags

        updated = app.state.db.update(existing)
        if not updated:
            raise HTTPException(status_code=500, detail="Failed to update idea")
        return updated.to_dict()

    @app.delete("/api/ideas/{idea_id}")
    async def delete_idea(idea_id: int) -> dict[str, str]:
        deleted = app.state.db.delete(idea_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Idea not found")
        return {"status": "deleted"}

    @app.get("/api/categories")
    async def get_categories() -> list[str]:
        return app.state.db.get_categories()

    @app.get("/api/search")
    async def search_ideas(q: str, limit: int = 50) -> dict[str, Any]:
        ideas = app.state.db.search(q, limit=limit)
        return {
            "ideas": [idea.to_dict() for idea in ideas],
            "query": q,
            "count": len(ideas),
        }

    @app.get("/api/stats")
    async def get_stats() -> dict[str, Any]:
        total = app.state.db.count()
        categories = app.state.db.get_categories()
        category_counts = {cat: app.state.db.count(cat) for cat in categories}
        return {
            "total": total,
            "categories": category_counts,
        }

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        return {"status": "healthy"}

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str) -> FileResponse:
        """Serve SPA shell for deep links."""
        if full_path.startswith("api/") or full_path.startswith("static/"):
            raise HTTPException(status_code=404, detail="Not found")
        return FileResponse(INDEX_FILE)

    return app


app = create_app()
