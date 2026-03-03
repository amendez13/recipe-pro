from pathlib import Path
import os
import shutil

import pytest
from fastapi import HTTPException

from app.app import _build_url_text_import_prompt, _run_claude_recipe_import


FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "import" / "hogarmania_pasta_e_ceci_page_text.txt"
SOURCE_URL = "https://www.hogarmania.com/cocina/recetas/pastas-pizzas/pasta-e-ceci.html"


def test_hogarmania_text_prompt_reproduces_incomplete_import_with_claude():
    if shutil.which("claude") is None:
        pytest.skip("claude CLI not available")
    if not FIXTURE_PATH.exists():
        pytest.skip("fixture not available")
    if not os.access(str(Path.home()), os.W_OK):
        pytest.skip("home directory not writable for claude runtime")

    page_text = FIXTURE_PATH.read_text(encoding="utf-8")
    prompt = _build_url_text_import_prompt(SOURCE_URL, page_text)

    try:
        _run_claude_recipe_import(prompt, allow_web_fetch=False)
    except HTTPException as exc:
        if exc.status_code == 502 and "EACCES" in str(exc.detail):
            pytest.skip("claude runtime cannot write state files in this environment")
        assert exc.status_code == 422
        assert "incomplete" in str(exc.detail).lower()
        return

    pytest.fail("Expected incomplete import failure was not reproduced")
