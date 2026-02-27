"""SQLite database layer for Idea Canvas."""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator, Optional

from .models import Idea

logger = logging.getLogger(__name__)


class IdeaDatabase:
    """SQLite-backed storage for ideas."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ideas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    tags TEXT DEFAULT '[]',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ideas_category ON ideas(category)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ideas_created_at ON ideas(created_at)
            """)
            conn.commit()

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _row_to_idea(self, row: sqlite3.Row) -> Idea:
        tags = json.loads(row["tags"]) if row["tags"] else []
        return Idea(
            id=row["id"],
            title=row["title"],
            content=row["content"],
            category=row["category"],
            tags=tags,
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None,
        )

    def create(self, idea: Idea) -> Idea:
        now = datetime.utcnow().isoformat()
        tags_json = json.dumps(idea.tags)

        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO ideas (title, content, category, tags, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (idea.title, idea.content, idea.category, tags_json, now, now),
            )
            conn.commit()
            idea.id = cursor.lastrowid
            idea.created_at = datetime.fromisoformat(now)
            idea.updated_at = datetime.fromisoformat(now)

        logger.info("Created idea id=%s title=%s", idea.id, idea.title)
        return idea

    def get(self, idea_id: int) -> Optional[Idea]:
        with self._connect() as conn:
            cursor = conn.execute("SELECT * FROM ideas WHERE id = ?", (idea_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_idea(row)
        return None

    def list_all(
        self,
        category: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Idea]:
        with self._connect() as conn:
            if category:
                cursor = conn.execute(
                    """
                    SELECT * FROM ideas WHERE category = ?
                    ORDER BY created_at DESC LIMIT ? OFFSET ?
                    """,
                    (category, limit, offset),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT * FROM ideas
                    ORDER BY created_at DESC LIMIT ? OFFSET ?
                    """,
                    (limit, offset),
                )
            return [self._row_to_idea(row) for row in cursor.fetchall()]

    def update(self, idea: Idea) -> Optional[Idea]:
        if idea.id is None:
            return None

        now = datetime.utcnow().isoformat()
        tags_json = json.dumps(idea.tags)

        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE ideas
                SET title = ?, content = ?, category = ?, tags = ?, updated_at = ?
                WHERE id = ?
                """,
                (idea.title, idea.content, idea.category, tags_json, now, idea.id),
            )
            conn.commit()
            if cursor.rowcount == 0:
                return None

        idea.updated_at = datetime.fromisoformat(now)
        logger.info("Updated idea id=%s", idea.id)
        return idea

    def delete(self, idea_id: int) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM ideas WHERE id = ?", (idea_id,))
            conn.commit()
            deleted = cursor.rowcount > 0

        if deleted:
            logger.info("Deleted idea id=%s", idea_id)
        return deleted

    def get_categories(self) -> list[str]:
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT DISTINCT category FROM ideas ORDER BY category"
            )
            return [row["category"] for row in cursor.fetchall()]

    def count(self, category: Optional[str] = None) -> int:
        with self._connect() as conn:
            if category:
                cursor = conn.execute(
                    "SELECT COUNT(*) as count FROM ideas WHERE category = ?",
                    (category,),
                )
            else:
                cursor = conn.execute("SELECT COUNT(*) as count FROM ideas")
            return cursor.fetchone()["count"]

    def search(self, query: str, limit: int = 50) -> list[Idea]:
        search_term = f"%{query}%"
        with self._connect() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM ideas
                WHERE title LIKE ? OR content LIKE ? OR tags LIKE ?
                ORDER BY created_at DESC LIMIT ?
                """,
                (search_term, search_term, search_term, limit),
            )
            return [self._row_to_idea(row) for row in cursor.fetchall()]
