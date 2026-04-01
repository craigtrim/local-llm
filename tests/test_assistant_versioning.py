"""Tests for assistant UUID and versioning (#29)."""

import re
from unittest.mock import patch

import pytest

from local_llm import assistants


@pytest.fixture(autouse=True)
def _tmp_assistants_dir(tmp_path):
    with patch("local_llm.assistants.ASSISTANTS_DIR", str(tmp_path)):
        yield tmp_path


def _make(name="Test", model="m", prompt="p", **kw):
    return assistants.save_assistant({"name": name, "model": model, "system_prompt": prompt, **kw})


def test_new_assistant_gets_uuid():
    saved = _make()
    assert "uuid" in saved
    assert len(saved["uuid"]) == 32


def test_uuid_is_valid_format():
    saved = _make()
    assert re.match(r"^[0-9a-f]{32}$", saved["uuid"])


def test_uuid_stable_across_edits():
    first = _make(name="Stable")
    uid = first["uuid"]
    second = assistants.save_assistant({"id": "stable", "name": "Stable", "model": "m2", "system_prompt": "p2"})
    assert second["uuid"] == uid


def test_version_starts_at_1():
    saved = _make()
    assert saved["version"] == 1


def test_version_increments_on_save():
    _make(name="Bump")
    v2 = assistants.save_assistant({"id": "bump", "name": "Bump", "model": "m", "system_prompt": "new"})
    assert v2["version"] == 2
    v3 = assistants.save_assistant({"id": "bump", "name": "Bump", "model": "m", "system_prompt": "newer"})
    assert v3["version"] == 3


def test_rename_preserves_uuid():
    original = _make(name="Old Name")
    uid = original["uuid"]
    renamed = assistants.save_assistant({"id": "old-name", "name": "New Name", "model": "m", "system_prompt": "p"})
    assert renamed["uuid"] == uid


def test_rename_changes_id():
    _make(name="Original")
    renamed = assistants.save_assistant({"id": "original", "name": "Renamed", "model": "m", "system_prompt": "p"})
    assert renamed["id"] == "renamed"


def test_old_id_file_removed_on_rename(_tmp_assistants_dir):
    _make(name="Before")
    assert (_tmp_assistants_dir / "before.json").exists()
    assistants.save_assistant({"id": "before", "name": "After", "model": "m", "system_prompt": "p"})
    assert not (_tmp_assistants_dir / "before.json").exists()
    assert (_tmp_assistants_dir / "after.json").exists()


def test_get_by_uuid():
    saved = _make(name="Findable")
    found = assistants.get_assistant_by_uuid(saved["uuid"])
    assert found is not None
    assert found["name"] == "Findable"


def test_get_by_stale_slug_returns_none():
    _make(name="Will Rename")
    assistants.save_assistant({"id": "will-rename", "name": "New Name", "model": "m", "system_prompt": "p"})
    assert assistants.get_assistant("will-rename") is None
