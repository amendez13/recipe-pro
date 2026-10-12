from pathlib import Path
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.app import _build_url_text_import_prompt, _run_claude_recipe_import


FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "import" / "hogarmania_pasta_e_ceci_page_text.txt"
SOURCE_URL = "https://www.hogarmania.com/cocina/recetas/pastas-pizzas/pasta-e-ceci.html"


@pytest.mark.parametrize("complete", [False, True], ids=["incomplete-rejected", "complete-normalized"])
def test_hogarmania_text_prompt_reproduces_incomplete_import_with_claude(monkeypatch, complete):
    # Recorded response shapes exercise both the original failure and the fixed
    # successful import without depending on provider output, auth, or billing.
    page_text = FIXTURE_PATH.read_text(encoding="utf-8")
    prompt = _build_url_text_import_prompt(SOURCE_URL, page_text)
    recipe = {
        "title": "Pasta e ceci",
        "source_url": SOURCE_URL,
        "steps": ["Cook the pasta and combine with chickpeas."],
        "ingredients": ([
            {"name_en": "pasta", "name_es": "pasta", "quantity": 250, "unit": "g"},
            {"name_en": "cooked chickpeas", "name_es": "garbanzos cocidos", "quantity": 300, "unit": "g"},
        ] if complete else []),
    }
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        assert command[0] == "claude"
        assert command[2] == prompt
        assert "PAGE_TEXT_BEGIN" in prompt and "PAGE_TEXT_END" in prompt
        assert "250 gr. de pasta para sopa" in prompt
        assert "300 gr. de garbanzos cocidos" in prompt
        assert "--allowedTools" not in command
        return SimpleNamespace(stdout=json.dumps({"type": "result", "is_error": False, "structured_output": recipe}))

    monkeypatch.setattr("app.app.subprocess.run", fake_run)
    if complete:
        result = _run_claude_recipe_import(prompt, allow_web_fetch=False)
        assert result["title"] == "Pasta e ceci"
        assert result["source_url"] == SOURCE_URL
        assert result["steps"] == recipe["steps"]
        assert [(i["name_en"], i["quantity"], i["unit"]) for i in result["ingredients"]] == [
            ("pasta", 250, "g"), ("cooked chickpeas", 300, "g")
        ]
    else:
        with pytest.raises(HTTPException) as exc_info:
            _run_claude_recipe_import(prompt, allow_web_fetch=False)
        assert exc_info.value.status_code == 422
        assert "incomplete" in str(exc_info.value.detail).lower()
    assert len(calls) == 1
