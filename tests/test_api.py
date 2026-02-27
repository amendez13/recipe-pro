from fastapi.testclient import TestClient
import pytest

from app.app import create_app
from app.config import Config, DatabaseConfig, WebConfig


@pytest.fixture
def client(tmp_path):
    cfg = Config(
        web=WebConfig(host="127.0.0.1", port=8084),
        database=DatabaseConfig(path=str(tmp_path / "api.db")),
    )
    return TestClient(create_app(cfg))


def create_recipe(client: TestClient, title: str = "Pasta") -> dict:
    payload = {
        "title": title,
        "steps": ["Step 1", "Step 2"],
        "servings": 2,
        "prep_time": 10,
        "cook_time": 20,
        "ingredients": [
            {"name": "Pasta", "quantity": 200, "unit": "g", "category": "pantry"},
            {"name": "Salt", "quantity": 1, "unit": "tsp", "category": "pantry"},
        ],
    }
    response = client.post("/api/recipes", json=payload)
    assert response.status_code == 201
    return response.json()


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_recipe_crud_and_search(client):
    created = create_recipe(client, "Pasta Carbonara")

    list_resp = client.get("/api/recipes")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    search_resp = client.get("/api/recipes?search=Carbon")
    assert search_resp.status_code == 200
    assert search_resp.json()[0]["title"] == "Pasta Carbonara"

    detail_resp = client.get(f"/api/recipes/{created['id']}")
    assert detail_resp.status_code == 200
    assert len(detail_resp.json()["ingredients"]) == 2
    assert detail_resp.json()["steps"] == ["Step 1", "Step 2"]

    update_payload = {
        "title": "Pasta Deluxe",
        "steps": ["Step 1 revised"],
        "servings": 4,
        "prep_time": 12,
        "cook_time": 25,
        "ingredients": [{"name": "Pasta", "quantity": 300, "unit": "g", "category": "pantry"}],
    }
    update_resp = client.put(f"/api/recipes/{created['id']}", json=update_payload)
    assert update_resp.status_code == 200
    assert update_resp.json()["title"] == "Pasta Deluxe"
    assert update_resp.json()["steps"] == ["Step 1 revised"]

    delete_resp = client.delete(f"/api/recipes/{created['id']}")
    assert delete_resp.status_code == 200
    assert delete_resp.json() == {"success": True}

    assert client.get(f"/api/recipes/{created['id']}").status_code == 404


def test_recipe_validation_error(client):
    response = client.post(
        "/api/recipes",
        json={"title": "", "steps": [], "ingredients": []},
    )
    assert response.status_code == 422


def test_ingredient_endpoints_and_404(client):
    create_recipe(client, "Soup")

    ingredients = client.get("/api/ingredients")
    assert ingredients.status_code == 200
    body = ingredients.json()
    assert len(body) >= 1
    assert "default_available" in body[0]

    ingredient_id = body[0]["id"]
    recipes = client.get(f"/api/ingredients/{ingredient_id}/recipes")
    assert recipes.status_code == 200
    assert len(recipes.json()) >= 1

    preference = client.post(
        f"/api/ingredients/{ingredient_id}/default",
        json={"default_available": True},
    )
    assert preference.status_code == 200
    assert preference.json()["default_available"] is True

    preference_post_base = client.post(
        f"/api/ingredients/{ingredient_id}",
        json={"default_available": False},
    )
    assert preference_post_base.status_code == 200
    assert preference_post_base.json()["default_available"] is False

    missing = client.get("/api/ingredients/999999/recipes")
    assert missing.status_code == 404


def test_stats_endpoint(client):
    create_recipe(client, "Salad")
    response = client.get("/api/stats")

    assert response.status_code == 200
    data = response.json()
    assert data["recipe_count"] == 1
    assert data["ingredient_count"] >= 1
    assert isinstance(data["category_counts"], dict)


def test_shopping_list_and_empty(client):
    r1 = create_recipe(client, "Soup")
    r2 = create_recipe(client, "Stew")

    empty = client.post("/api/shopping-list", json={"recipe_ids": []})
    assert empty.status_code == 200
    assert empty.json() == {"items": [], "by_category": {}}

    response = client.post("/api/shopping-list", json={"recipe_ids": [r1["id"], r2["id"]]})
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) >= 1
    assert "by_category" in data


def test_suggestions_endpoint(client):
    create_recipe(client, "Pasta")
    create_recipe(
        client,
        "Egg Dish",
    )
    ingredients = client.get("/api/ingredients").json()
    salt = next(i for i in ingredients if i["name"] == "salt")

    response = client.post("/api/suggestions", json={"ingredient_ids": [salt["id"]]})
    assert response.status_code == 200
    data = response.json()
    assert "suggestions" in data
    assert len(data["suggestions"]) >= 1
