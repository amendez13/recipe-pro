"""Tests for Idea Canvas API."""

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Config, DatabaseConfig, WebConfig
from app.app import create_app


@pytest.fixture
def test_config(tmp_path):
    """Create a test config with temporary database."""
    return Config(
        web=WebConfig(host="127.0.0.1", port=8084),
        database=DatabaseConfig(path=str(tmp_path / "test.db")),
    )


@pytest.fixture
def client(test_config):
    """Create a test client."""
    app = create_app(test_config)
    return TestClient(app)


def test_health_check(client):
    """Test health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_list_ideas_empty(client):
    """Test listing ideas when empty."""
    response = client.get("/api/ideas")
    assert response.status_code == 200
    data = response.json()
    assert data["ideas"] == []
    assert data["total"] == 0


def test_create_idea(client):
    """Test creating an idea."""
    idea_data = {
        "title": "Test Idea",
        "content": "This is a test idea.",
        "category": "test",
        "tags": ["tag1", "tag2"],
    }
    response = client.post("/api/ideas", json=idea_data)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Idea"
    assert data["content"] == "This is a test idea."
    assert data["category"] == "test"
    assert data["tags"] == ["tag1", "tag2"]
    assert data["id"] is not None


def test_get_idea(client):
    """Test getting a specific idea."""
    # Create an idea first
    idea_data = {"title": "Get Test", "content": "Content", "category": "general", "tags": []}
    create_response = client.post("/api/ideas", json=idea_data)
    idea_id = create_response.json()["id"]

    # Get the idea
    response = client.get(f"/api/ideas/{idea_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Get Test"


def test_update_idea(client):
    """Test updating an idea."""
    # Create an idea
    idea_data = {"title": "Original", "content": "Original content", "category": "general", "tags": []}
    create_response = client.post("/api/ideas", json=idea_data)
    idea_id = create_response.json()["id"]

    # Update it
    update_data = {"title": "Updated", "content": "Updated content"}
    response = client.put(f"/api/ideas/{idea_id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated"
    assert data["content"] == "Updated content"


def test_delete_idea(client):
    """Test deleting an idea."""
    # Create an idea
    idea_data = {"title": "To Delete", "content": "Will be deleted", "category": "general", "tags": []}
    create_response = client.post("/api/ideas", json=idea_data)
    idea_id = create_response.json()["id"]

    # Delete it
    response = client.delete(f"/api/ideas/{idea_id}")
    assert response.status_code == 200

    # Verify it's gone
    get_response = client.get(f"/api/ideas/{idea_id}")
    assert get_response.status_code == 404


def test_search_ideas(client):
    """Test searching ideas."""
    # Create some ideas
    client.post("/api/ideas", json={"title": "Python Tips", "content": "Tips for Python", "category": "programming", "tags": []})
    client.post("/api/ideas", json={"title": "JavaScript Guide", "content": "Guide for JS", "category": "programming", "tags": []})

    # Search
    response = client.get("/api/search?q=Python")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["ideas"][0]["title"] == "Python Tips"


def test_get_categories(client):
    """Test getting categories."""
    # Create ideas with different categories
    client.post("/api/ideas", json={"title": "Idea 1", "content": "", "category": "alpha", "tags": []})
    client.post("/api/ideas", json={"title": "Idea 2", "content": "", "category": "beta", "tags": []})

    response = client.get("/api/categories")
    assert response.status_code == 200
    categories = response.json()
    assert "alpha" in categories
    assert "beta" in categories


def test_get_stats(client):
    """Test getting stats."""
    # Create some ideas
    client.post("/api/ideas", json={"title": "Idea 1", "content": "", "category": "cat1", "tags": []})
    client.post("/api/ideas", json={"title": "Idea 2", "content": "", "category": "cat1", "tags": []})
    client.post("/api/ideas", json={"title": "Idea 3", "content": "", "category": "cat2", "tags": []})

    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert data["categories"]["cat1"] == 2
    assert data["categories"]["cat2"] == 1
