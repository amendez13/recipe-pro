from app.database import RecipeDatabase


def recipe_payload(title: str = "Pasta") -> dict:
    return {
        "title": title,
        "url": "https://example.com/pasta",
        "steps": ["Boil water", "Cook pasta"],
        "servings": 2,
        "prep_time": 10,
        "cook_time": 15,
        "ingredients": [
            {"name": "Pasta", "quantity": 200, "unit": "g", "category": "pantry"},
            {"name": "Salt", "quantity": 1, "unit": "tsp", "category": "pantry"},
        ],
    }


def test_ingredient_normalization_and_dedup(tmp_path):
    db = RecipeDatabase(tmp_path / "test.db")
    a = db.get_or_create_ingredient("  ONION  ", "produce")
    b = db.get_or_create_ingredient("onion", "produce")

    assert a.id == b.id
    assert b.name == "onion"
    assert b.default_available is False

    updated = db.update_ingredient_default_available(b.id, True)
    assert updated is not None
    assert updated.default_available is True


def test_recipe_crud_and_joined_ingredients(tmp_path):
    db = RecipeDatabase(tmp_path / "test.db")

    created = db.create_recipe(recipe_payload())
    assert created.id is not None
    assert len(created.ingredients) == 2
    assert [step.instruction for step in created.steps] == ["Boil water", "Cook pasta"]

    loaded = db.get_recipe_by_id(created.id)
    assert loaded is not None
    assert loaded.title == "Pasta"
    assert loaded.url == "https://example.com/pasta"
    assert {i.ingredient.name for i in loaded.ingredients if i.ingredient} == {"pasta", "salt"}

    updated = db.update_recipe(
        created.id,
        {
            "title": "Better Pasta",
            "url": "https://example.com/better-pasta",
            "steps": ["Step 1"],
            "servings": 3,
            "prep_time": 12,
            "cook_time": 18,
            "ingredients": [
                {"name": "Pasta", "quantity": 250, "unit": "g", "category": "pantry"},
                {"name": "Garlic", "quantity": 2, "unit": "cloves", "category": "produce"},
            ],
        },
    )
    assert updated is not None
    assert updated.title == "Better Pasta"
    assert updated.url == "https://example.com/better-pasta"
    assert [step.instruction for step in updated.steps] == ["Step 1"]
    assert {i.ingredient.name for i in updated.ingredients if i.ingredient} == {"pasta", "garlic"}

    deleted = db.delete_recipe(created.id)
    assert deleted is True
    assert db.get_recipe_by_id(created.id) is None


def test_shopping_list_mixed_units_and_empty_input(tmp_path):
    db = RecipeDatabase(tmp_path / "test.db")
    r1 = db.create_recipe(
        {
            "title": "Soup",
            "steps": ["Cook"],
            "ingredients": [
                {"name": "Onion", "quantity": 1, "unit": "piece", "category": "produce"},
                {"name": "Salt", "quantity": 1, "unit": "tsp", "category": "pantry"},
            ],
        }
    )
    r2 = db.create_recipe(
        {
            "title": "Stew",
            "steps": ["Cook"],
            "ingredients": [
                {"name": "Onion", "quantity": 200, "unit": "g", "category": "produce"},
                {"name": "Salt", "quantity": 2, "unit": "tsp", "category": "pantry"},
            ],
        }
    )

    empty = db.get_shopping_list([])
    assert empty == {"items": [], "by_category": {}}

    shopping = db.get_shopping_list([r1.id, r2.id])
    salt = [i for i in shopping["items"] if i["name"] == "salt" and i["unit"] == "tsp"][0]
    onions = [i for i in shopping["items"] if i["name"] == "onion"]

    assert salt["total_quantity"] == 3
    assert len(onions) == 2  # units differ, so separate rows


def test_suggestions_ranking_and_no_match_behavior(tmp_path):
    db = RecipeDatabase(tmp_path / "test.db")
    pasta = db.create_recipe(
        {
            "title": "Pasta",
            "steps": ["Cook"],
            "ingredients": [
                {"name": "Pasta", "quantity": 1, "unit": "box", "category": "pantry"},
                {"name": "Egg", "quantity": 2, "unit": "piece", "category": "dairy"},
            ],
        }
    )
    omelet = db.create_recipe(
        {
            "title": "Omelet",
            "steps": ["Cook"],
            "ingredients": [
                {"name": "Egg", "quantity": 3, "unit": "piece", "category": "dairy"},
                {"name": "Milk", "quantity": 100, "unit": "ml", "category": "dairy"},
            ],
        }
    )

    egg = next(i for i in db.get_all_ingredients() if i.name == "egg")
    suggestions = db.get_recipe_suggestions([egg.id])

    assert len(suggestions) == 2
    assert suggestions[0]["match_percentage"] >= suggestions[1]["match_percentage"]
    assert suggestions[0]["recipe"]["id"] in {pasta.id, omelet.id}

    no_match = db.get_recipe_suggestions([99999])
    assert no_match == []


def test_recipe_steps_fallback_from_instructions(tmp_path):
    db = RecipeDatabase(tmp_path / "test.db")
    created = db.create_recipe(
        {
            "title": "Legacy Recipe",
            "instructions": "First line\nSecond line",
            "ingredients": [{"name": "Salt", "quantity": 1, "unit": "tsp", "category": "pantry"}],
        }
    )
    assert [step.instruction for step in created.steps] == ["First line", "Second line"]


def test_ingredient_merge_preview_merge_and_undo(tmp_path):
    db = RecipeDatabase(tmp_path / "test.db")
    recipe_a = db.create_recipe(
        {
            "title": "A",
            "steps": ["Cook"],
            "ingredients": [
                {"name": "olive oil", "quantity": 1, "unit": "tbsp"},
                {"name": "extra virgin olive oil", "quantity": 2, "unit": "tbsp"},
            ],
        }
    )
    recipe_b = db.create_recipe(
        {
            "title": "B",
            "steps": ["Cook"],
            "ingredients": [
                {"name": "extra virgin olive oil", "quantity": 3, "unit": "tbsp"},
            ],
        }
    )

    ingredients = db.get_all_ingredients()
    primary = next(i for i in ingredients if i.name == "olive oil")
    secondary = next(i for i in ingredients if i.name == "extra virgin olive oil")

    preview = db.get_ingredient_merge_preview(primary.id, secondary.id)
    assert preview["secondary_recipe_count"] == 2
    assert preview["collision_recipe_count"] == 1

    merged = db.merge_ingredients(primary.id, secondary.id, confirm_collision_drop=True)
    assert merged["dropped_collision_rows"] == 1
    assert merged["repointed_rows"] == 1
    assert db.get_ingredient_by_id(secondary.id) is None

    recipe_a_loaded = db.get_recipe_by_id(recipe_a.id)
    recipe_b_loaded = db.get_recipe_by_id(recipe_b.id)
    assert recipe_a_loaded is not None
    assert recipe_b_loaded is not None
    names_a = [row.ingredient.name for row in recipe_a_loaded.ingredients if row.ingredient]
    names_b = [row.ingredient.name for row in recipe_b_loaded.ingredients if row.ingredient]
    assert names_a.count("olive oil") == 1
    assert "extra virgin olive oil" not in names_a
    assert names_b == ["olive oil"]

    undone = db.undo_ingredient_merge(merged["merge_event_id"])
    restored_name = undone["restored_secondary_name"]
    restored = next(i for i in db.get_all_ingredients() if i.name == restored_name)
    assert restored is not None
    restored_preview = db.get_ingredient_merge_preview(primary.id, restored.id)
    assert restored_preview["secondary_recipe_count"] == 2
