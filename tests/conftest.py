"""Keep the default test suite independent of paid model providers."""

from pathlib import Path
import json
import subprocess
from types import SimpleNamespace

import pytest


@pytest.fixture(autouse=True)
def block_live_claude_calls(monkeypatch):
    original_run = subprocess.run
    import app.app as recipe_app

    monkeypatch.setattr(recipe_app, "_INGREDIENT_TRANSLATION_CACHE", {})
    monkeypatch.setattr(recipe_app, "_CLAUDE_TRANSLATION_AVAILABLE", None)
    monkeypatch.setattr(recipe_app, "_CLAUDE_TRANSLATION_UNAVAILABLE_UNTIL", 0.0)

    def guarded_run(command, *args, **kwargs):
        executable = command if isinstance(command, str) else str(command[0])
        if Path(executable.split()[0]).name == "claude":
            # CRUD cases do not test translation quality. Return stable names at
            # the provider boundary; dedicated translation cases override this
            # stub with their own bilingual responses and exercise real parsing.
            if not isinstance(command, str) and "INPUT_NAME: " in command[2]:
                name = command[2].rsplit("INPUT_NAME: ", 1)[1]
                return SimpleNamespace(stdout=json.dumps({
                    "type": "result", "is_error": False,
                    "structured_output": {"name_en": name, "name_es": name},
                }))
            raise AssertionError("Mock Claude responses in tests; live provider calls are disabled")
        return original_run(command, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", guarded_run)
