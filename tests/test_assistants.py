"""Unit tests for the assistants module (CRUD, validation, defaults)."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from local_llm import assistants


@pytest.fixture(autouse=True)
def _tmp_assistants_dir(tmp_path):
    """Point ASSISTANTS_DIR to a temp directory for isolation."""
    with patch("local_llm.assistants.ASSISTANTS_DIR", str(tmp_path)):
        yield tmp_path


# --- Default assistant ---


def test_default_assistant_always_present():
    result = assistants.list_assistants()
    assert len(result) >= 1
    assert result[0]["id"] == "default"
    assert result[0]["name"] == "Default"


def test_default_assistant_has_no_model():
    default = assistants.get_assistant("default")
    assert default is not None
    assert default["model"] is None


def test_default_assistant_not_deletable():
    with pytest.raises(ValueError, match="Cannot delete"):
        assistants.delete_assistant("default")


# --- Save / get ---


def test_save_and_get_assistant():
    config = {
        "name": "Code Reviewer",
        "model": "codellama:13b",
        "system_prompt": "You review code.",
        "avatar_color": "#4a9f4a",
    }
    saved = assistants.save_assistant(config)
    assert saved["id"] == "code-reviewer"
    assert saved["name"] == "Code Reviewer"

    loaded = assistants.get_assistant("code-reviewer")
    assert loaded is not None
    assert loaded["model"] == "codellama:13b"
    assert loaded["system_prompt"] == "You review code."


def test_save_generates_id_from_name():
    config = {
        "name": "My Test Assistant!",
        "model": "test-model",
        "system_prompt": "Hello.",
    }
    saved = assistants.save_assistant(config)
    assert saved["id"] == "my-test-assistant"


def test_save_preserves_explicit_id():
    config = {
        "id": "custom-id",
        "name": "Custom",
        "model": "test-model",
        "system_prompt": "Hello.",
    }
    saved = assistants.save_assistant(config)
    assert saved["id"] == "custom-id"


def test_save_creates_json_file(_tmp_assistants_dir):
    config = {
        "name": "Writer",
        "model": "llama3",
        "system_prompt": "You write stories.",
    }
    assistants.save_assistant(config)
    path = _tmp_assistants_dir / "writer.json"
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["name"] == "Writer"
    assert data["system_prompt"] == "You write stories."


# --- Validation ---


def test_save_rejects_missing_name():
    with pytest.raises(ValueError, match="'name' is required"):
        assistants.save_assistant({"model": "x", "system_prompt": "y"})


def test_save_rejects_missing_model_for_custom():
    with pytest.raises(ValueError, match="'model' is required"):
        assistants.save_assistant({"name": "Foo", "system_prompt": "y"})


def test_save_rejects_missing_system_prompt():
    with pytest.raises(ValueError, match="'system_prompt' is required"):
        assistants.save_assistant({"name": "Foo", "model": "x"})


def test_save_rejects_bad_color():
    with pytest.raises(ValueError, match="avatar_color"):
        assistants.save_assistant({
            "name": "Foo",
            "model": "x",
            "system_prompt": "y",
            "avatar_color": "red",
        })


def test_save_accepts_valid_hex_color():
    config = {
        "name": "Colored",
        "model": "x",
        "system_prompt": "y",
        "avatar_color": "#FF00aa",
    }
    saved = assistants.save_assistant(config)
    assert saved["avatar_color"] == "#FF00aa"


def test_save_rejects_negative_context_tokens():
    with pytest.raises(ValueError, match="context_tokens"):
        assistants.save_assistant({
            "name": "Foo",
            "model": "x",
            "system_prompt": "y",
            "context_tokens": -100,
        })


def test_save_rejects_negative_token_ratio():
    with pytest.raises(ValueError, match="token_estimate_ratio"):
        assistants.save_assistant({
            "name": "Foo",
            "model": "x",
            "system_prompt": "y",
            "token_estimate_ratio": -1.0,
        })


def test_default_allows_null_model():
    """Default assistant is special: model can be null."""
    config = {
        "id": "default",
        "name": "Default",
        "system_prompt": "You are helpful.",
    }
    saved = assistants.save_assistant(config)
    assert saved["id"] == "default"


# --- List ---


def test_list_assistants_includes_saved():
    assistants.save_assistant({
        "name": "Alpha", "model": "a", "system_prompt": "a",
    })
    assistants.save_assistant({
        "name": "Beta", "model": "b", "system_prompt": "b",
    })
    result = assistants.list_assistants()
    names = [a["name"] for a in result]
    assert "Default" in names
    assert "Alpha" in names
    assert "Beta" in names


def test_list_default_first():
    assistants.save_assistant({
        "name": "Zzz Last", "model": "x", "system_prompt": "x",
    })
    result = assistants.list_assistants()
    assert result[0]["id"] == "default"


def test_list_skips_invalid_json(_tmp_assistants_dir):
    """Corrupted JSON files are skipped, not crash the list."""
    (_tmp_assistants_dir / "bad.json").write_text("{invalid json")
    result = assistants.list_assistants()
    ids = [a["id"] for a in result]
    assert "bad" not in ids


# --- Delete ---


def test_delete_assistant():
    assistants.save_assistant({
        "name": "Temp", "model": "x", "system_prompt": "x",
    })
    assert assistants.get_assistant("temp") is not None
    assert assistants.delete_assistant("temp") is True
    assert assistants.get_assistant("temp") is None


def test_delete_nonexistent_returns_false():
    assert assistants.delete_assistant("no-such-thing") is False


# --- Get ---


def test_get_nonexistent_returns_none():
    assert assistants.get_assistant("does-not-exist") is None


def test_get_default_from_disk(_tmp_assistants_dir):
    """If default.json exists on disk, get_assistant reads it."""
    data = {
        "id": "default",
        "name": "My Default",
        "model": "custom-model",
        "system_prompt": "Custom prompt.",
    }
    (_tmp_assistants_dir / "default.json").write_text(json.dumps(data))
    loaded = assistants.get_assistant("default")
    assert loaded["name"] == "My Default"
    assert loaded["model"] == "custom-model"
