"""Data models for Recipe Pro."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Ingredient:
    id: Optional[int] = None
    name: str = ""
    category: Optional[str] = None

    @classmethod
    def from_row(cls, row: dict) -> "Ingredient":
        return cls(
            id=row.get("id"),
            name=row.get("name", ""),
            category=row.get("category"),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
        }


@dataclass
class RecipeIngredient:
    id: Optional[int] = None
    recipe_id: Optional[int] = None
    ingredient_id: Optional[int] = None
    quantity: float = 0.0
    unit: str = ""
    notes: Optional[str] = None
    ingredient: Optional[Ingredient] = None

    @classmethod
    def from_row(cls, row: dict) -> "RecipeIngredient":
        ingredient = None
        ingredient_id = row.get("ingredient_id")
        ingredient_name = row.get("ingredient_name")
        if ingredient_id is not None and ingredient_name is not None:
            ingredient = Ingredient(
                id=ingredient_id,
                name=ingredient_name,
                category=row.get("ingredient_category"),
            )

        return cls(
            id=row.get("id"),
            recipe_id=row.get("recipe_id"),
            ingredient_id=ingredient_id,
            quantity=float(row.get("quantity") or 0.0),
            unit=row.get("unit", ""),
            notes=row.get("notes"),
            ingredient=ingredient,
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "recipe_id": self.recipe_id,
            "ingredient_id": self.ingredient_id,
            "quantity": self.quantity,
            "unit": self.unit,
            "notes": self.notes,
            "ingredient": self.ingredient.to_dict() if self.ingredient else None,
        }


@dataclass
class Recipe:
    id: Optional[int] = None
    title: str = ""
    instructions: str = ""
    servings: Optional[int] = None
    prep_time: Optional[int] = None
    cook_time: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    ingredients: list[RecipeIngredient] = field(default_factory=list)

    @classmethod
    def from_row(cls, row: dict) -> "Recipe":
        created_at = _parse_datetime(row.get("created_at"))
        updated_at = _parse_datetime(row.get("updated_at"))
        return cls(
            id=row.get("id"),
            title=row.get("title", ""),
            instructions=row.get("instructions", ""),
            servings=row.get("servings"),
            prep_time=row.get("prep_time"),
            cook_time=row.get("cook_time"),
            created_at=created_at,
            updated_at=updated_at,
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "instructions": self.instructions,
            "servings": self.servings,
            "prep_time": self.prep_time,
            "cook_time": self.cook_time,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "ingredients": [item.to_dict() for item in self.ingredients],
        }


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        # SQLite CURRENT_TIMESTAMP format: "YYYY-MM-DD HH:MM:SS"
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
