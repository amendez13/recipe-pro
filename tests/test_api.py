from fastapi.testclient import TestClient
import pytest

from app.app import _extract_recipe_from_url, create_app
from app.auth import hash_password
from app.config import AuthConfig, Config, DatabaseConfig, UserConfig, WebConfig


@pytest.fixture
def client(tmp_path):
    user1_hash = hash_password("alice-pass")
    user2_hash = hash_password("bob-pass")
    cfg = Config(
        web=WebConfig(host="127.0.0.1", port=8084),
        database=DatabaseConfig(path=str(tmp_path / "api.db")),
        auth=AuthConfig(
            session_secret="test-session-secret",
            users=[
                UserConfig(
                    username="alice",
                    password_hash=user1_hash,
                    db_path=str(tmp_path / "alice.db"),
                ),
                UserConfig(
                    username="bob",
                    password_hash=user2_hash,
                    db_path=str(tmp_path / "bob.db"),
                ),
            ],
        ),
    )
    test_client = TestClient(create_app(cfg))
    login = test_client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "alice-pass", "remember": True},
    )
    assert login.status_code == 200
    return test_client


@pytest.fixture
def auth_client(tmp_path):
    user1_hash = hash_password("alice-pass")
    user2_hash = hash_password("bob-pass")
    cfg = Config(
        web=WebConfig(host="127.0.0.1", port=8084),
        database=DatabaseConfig(path=str(tmp_path / "api.db")),
        auth=AuthConfig(
            session_secret="test-session-secret",
            users=[
                UserConfig(
                    username="alice",
                    password_hash=user1_hash,
                    db_path=str(tmp_path / "alice.db"),
                ),
                UserConfig(
                    username="bob",
                    password_hash=user2_hash,
                    db_path=str(tmp_path / "bob.db"),
                ),
            ],
        ),
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


def test_auth_login_me_logout(auth_client):
    me_before = auth_client.get("/api/auth/me")
    assert me_before.status_code == 401

    bad_login = auth_client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "wrong", "remember": True},
    )
    assert bad_login.status_code == 401

    login = auth_client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "alice-pass", "remember": True},
    )
    assert login.status_code == 200
    assert login.json()["username"] == "alice"

    me_after = auth_client.get("/api/auth/me")
    assert me_after.status_code == 200
    assert me_after.json() == {"username": "alice"}

    logout = auth_client.post("/api/auth/logout")
    assert logout.status_code == 200

    me_after_logout = auth_client.get("/api/auth/me")
    assert me_after_logout.status_code == 401


def test_auth_required_for_protected_endpoints(auth_client):
    response = auth_client.get("/api/recipes")
    assert response.status_code == 401
    response = auth_client.get("/api/ingredients")
    assert response.status_code == 401


def test_multi_user_data_isolation(tmp_path):
    cfg = Config(
        web=WebConfig(host="127.0.0.1", port=8084),
        database=DatabaseConfig(path=str(tmp_path / "api.db")),
        auth=AuthConfig(
            session_secret="isolation-secret",
            users=[
                UserConfig(
                    username="alice",
                    password_hash=hash_password("alice-pass"),
                    db_path=str(tmp_path / "alice.db"),
                ),
                UserConfig(
                    username="bob",
                    password_hash=hash_password("bob-pass"),
                    db_path=str(tmp_path / "bob.db"),
                ),
            ],
        ),
    )

    app = create_app(cfg)
    alice = TestClient(app)
    bob = TestClient(app)

    assert alice.post("/api/auth/login", json={"username": "alice", "password": "alice-pass"}).status_code == 200
    assert bob.post("/api/auth/login", json={"username": "bob", "password": "bob-pass"}).status_code == 200

    alice_recipe = {
        "title": "Alice Soup",
        "steps": ["Boil water"],
        "ingredients": [{"name": "Water", "quantity": 1, "unit": "cup"}],
    }
    bob_recipe = {
        "title": "Bob Pasta",
        "steps": ["Cook pasta"],
        "ingredients": [{"name": "Pasta", "quantity": 1, "unit": "cup"}],
    }

    assert alice.post("/api/recipes", json=alice_recipe).status_code == 201
    assert bob.post("/api/recipes", json=bob_recipe).status_code == 201

    alice_titles = [item["title"] for item in alice.get("/api/recipes").json()]
    bob_titles = [item["title"] for item in bob.get("/api/recipes").json()]

    assert alice_titles == ["Alice Soup"]
    assert bob_titles == ["Bob Pasta"]


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


def test_recipe_import_preview_endpoint(client, monkeypatch):
    class DummyResult:
        stdout = """
        {"type":"result","is_error":false,"result":"{\\"title\\":\\"Imported Recipe\\",\\"source_url\\":\\"https://example.com/r\\",\\"servings\\":2,\\"prep_time\\":10,\\"cook_time\\":20,\\"steps\\":[\\"Step one\\",\\"Step two\\"],\\"ingredients\\":[{\\"name\\":\\"Salt\\",\\"quantity\\":1,\\"unit\\":\\"tsp\\",\\"category\\":\\"spices\\",\\"notes\\":\\"\\"}]}"}
        """

    def fake_run(*args, **kwargs):
        return DummyResult()

    monkeypatch.setattr("app.app.subprocess.run", fake_run)

    response = client.post(
        "/api/recipes/import-preview",
        json={"url": "https://example.com/recipe"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Imported Recipe"
    assert len(body["steps"]) == 2
    assert len(body["ingredients"]) == 1


def test_recipe_import_preview_text_payload(client, monkeypatch):
    class DummyResult:
        stdout = """
        {"type":"result","is_error":false,"result":"{\\"title\\":\\"Imported From Text\\",\\"source_url\\":null,\\"servings\\":3,\\"prep_time\\":5,\\"cook_time\\":25,\\"steps\\":[\\"Mix\\",\\"Cook\\"],\\"ingredients\\":[{\\"name\\":\\"Rice\\",\\"quantity\\":1,\\"unit\\":\\"cup\\",\\"category\\":\\"pantry\\",\\"notes\\":\\"\\"}]}"}
        """

    def fake_run(*args, **kwargs):
        return DummyResult()

    monkeypatch.setattr("app.app.subprocess.run", fake_run)

    response = client.post(
        "/api/recipes/import-preview",
        json={"text": "Title: Imported From Text\nIngredients: 1 cup rice\nSteps: Mix then cook"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Imported From Text"
    assert len(body["steps"]) == 2
    assert len(body["ingredients"]) == 1


def test_recipe_import_preview_rejects_missing_input(client):
    response = client.post("/api/recipes/import-preview", json={})
    assert response.status_code == 422


def test_recipe_import_preview_rejects_both_inputs(client):
    response = client.post(
        "/api/recipes/import-preview",
        json={"url": "https://example.com/recipe", "text": "some text"},
    )
    assert response.status_code == 422


def test_recipe_import_preview_parses_fenced_json(client, monkeypatch):
    class DummyResult:
        stdout = """
        {"type":"result","is_error":false,"result":"```json\n{\n  \\"title\\": \\"Fenced Recipe\\",\n  \\"servings\\": 4,\n  \\"prep_time\\": 15,\n  \\"cook_time\\": 45,\n  \\"steps\\": [\\"Prep\\", \\"Bake\\"],\n  \\"ingredients\\": [{\\"name\\": \\"Noodles\\", \\"quantity\\": 12, \\"unit\\": \\"oz\\", \\"category\\": \\"pantry\\", \\"notes\\": \\"\\"}]\n}\n```"}
        """

    def fake_run(*args, **kwargs):
        return DummyResult()

    monkeypatch.setattr("app.app.subprocess.run", fake_run)

    response = client.post("/api/recipes/import-preview", json={"url": "https://example.com/fenced"})
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Fenced Recipe"
    assert body["steps"] == ["Prep", "Bake"]
    assert len(body["ingredients"]) == 1


def test_recipe_import_preview_normalizes_null_source_and_unit(client, monkeypatch):
    class DummyResult:
        stdout = """
        {"type":"result","is_error":false,"result":"{\\"title\\":\\"Null Fields\\",\\"source_url\\":null,\\"servings\\":2,\\"prep_time\\":1,\\"cook_time\\":2,\\"steps\\":[\\"Only step\\"],\\"ingredients\\":[{\\"name\\":\\"Eggs\\",\\"quantity\\":2,\\"unit\\":null,\\"category\\":null,\\"notes\\":null}]}"}
        """

    def fake_run(*args, **kwargs):
        return DummyResult()

    monkeypatch.setattr("app.app.subprocess.run", fake_run)

    response = client.post("/api/recipes/import-preview", json={"text": "eggs recipe"})
    assert response.status_code == 422


def test_extract_recipe_from_url_json_ld(monkeypatch):
    class DummyResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b"""
            <html><head>
            <script type="application/ld+json">
            {
              "@context": "https://schema.org",
              "@type": "Recipe",
              "name": "Test Lasagna",
              "recipeYield": "8 servings",
              "prepTime": "PT20M",
              "cookTime": "PT1H",
              "recipeIngredient": ["1 lb beef", "2 cups cheese"],
              "recipeInstructions": [
                {"@type":"HowToStep","text":"Brown the meat."},
                {"@type":"HowToStep","text":"Layer and bake."}
              ]
            }
            </script>
            </head><body></body></html>
            """

    def fake_urlopen(*args, **kwargs):
        return DummyResponse()

    monkeypatch.setattr("app.app.urlopen", fake_urlopen)
    recipe = _extract_recipe_from_url("https://example.com/lasagna")
    assert recipe is not None
    assert recipe["title"] == "Test Lasagna"
    assert recipe["servings"] == 8
    assert recipe["prep_time"] == 20
    assert recipe["cook_time"] == 60
    assert recipe["steps"] == ["Brown the meat.", "Layer and bake."]
    assert len(recipe["ingredients"]) == 2
