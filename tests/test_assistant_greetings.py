"""Ensure all assistants on disk have greetings (#46)."""

import json
from pathlib import Path

from local_llm.config import ASSISTANTS_DIR


def test_all_assistants_have_greetings():
    """Every assistant JSON file must have a non-empty greetings list."""
    assistants_dir = Path(ASSISTANTS_DIR).expanduser()
    if not assistants_dir.exists():
        return

    files = list(assistants_dir.glob("*.json"))
    assert files, f"No assistant files found in {assistants_dir}"

    for path in files:
        data = json.loads(path.read_text())
        name = data.get("name", path.stem)
        greetings = data.get("greetings")
        assert isinstance(greetings, list) and len(greetings) > 0, (
            f"Assistant '{name}' ({path.name}) has no greetings"
        )
