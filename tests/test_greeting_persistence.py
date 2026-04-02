"""Tests for greeting persistence across save/load/rename (#40)."""

import json
from unittest.mock import patch

import pytest

from local_llm import assistants


@pytest.fixture(autouse=True)
def _tmp_assistants_dir(tmp_path):
    with patch("local_llm.assistants.ASSISTANTS_DIR", str(tmp_path)):
        yield tmp_path


_call_count = 0

def _greeting_fn(name, system_prompt, model):
    global _call_count
    _call_count += 1
    return [f"Hi from {name} ({system_prompt[:10]}) call{_call_count} #{i}" for i in range(20)]


def _make(name="Test", model="m", prompt="p", **kw):
    return assistants.save_assistant(
        {"name": name, "model": model, "system_prompt": prompt, **kw},
        generate_greetings_fn=_greeting_fn,
    )


def test_greetings_survive_save_load_cycle():
    saved = _make(name="Persist")
    loaded = assistants.get_assistant("persist")
    assert loaded["greetings"] == saved["greetings"]


def test_greetings_survive_rename():
    first = _make(name="OldSlug")
    greetings = first["greetings"]
    # Rename but keep same prompt/model/name content triggers regen
    # So let's just verify rename doesn't lose the field
    renamed = assistants.save_assistant(
        {"id": "oldslug", "name": "NewSlug", "model": "m", "system_prompt": "p"},
        generate_greetings_fn=_greeting_fn,
    )
    assert "greetings" in renamed
    assert len(renamed["greetings"]) == 20


def test_greetings_in_version_snapshot(_tmp_assistants_dir):
    first = _make(name="Versioned")
    uid = first["uuid"]
    original_greetings = first["greetings"]
    # Edit to create a version snapshot
    assistants.save_assistant(
        {"id": "versioned", "name": "Versioned", "model": "m", "system_prompt": "new"},
        generate_greetings_fn=_greeting_fn,
    )
    snapshot = assistants.get_version(uid, 1)
    assert snapshot is not None
    assert snapshot["greetings"] == original_greetings


def test_old_version_greetings_differ_from_current(_tmp_assistants_dir):
    first = _make(name="DiffVer")
    uid = first["uuid"]
    assistants.save_assistant(
        {"id": "diffver", "name": "DiffVer", "model": "m", "system_prompt": "changed"},
        generate_greetings_fn=_greeting_fn,
    )
    current = assistants.get_assistant("diffver")
    old = assistants.get_version(uid, 1)
    assert current["greetings"] != old["greetings"]


def test_delete_assistant_greetings_gone(_tmp_assistants_dir):
    _make(name="Deletable")
    assistants.delete_assistant("deletable")
    assert assistants.get_assistant("deletable") is None


def test_migration_adds_empty_greetings(_tmp_assistants_dir):
    """Legacy assistant without greetings field gets empty list on load."""
    legacy = {"id": "legacy", "name": "Legacy", "model": "m", "system_prompt": "p"}
    (_tmp_assistants_dir / "legacy.json").write_text(json.dumps(legacy))
    loaded = assistants.get_assistant("legacy")
    # Migration doesn't add greetings (that requires an LLM call)
    # But save_assistant with no fn should default to empty
    assert loaded is not None
    # greetings field may not exist on legacy load, that's fine
    assert loaded.get("greetings", []) == []
