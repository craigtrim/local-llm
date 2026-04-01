"""Tests for migrating legacy assistants without UUID/version (#29)."""

import json
from unittest.mock import patch

import pytest

from local_llm import assistants


@pytest.fixture(autouse=True)
def _tmp_assistants_dir(tmp_path):
    with patch("local_llm.assistants.ASSISTANTS_DIR", str(tmp_path)):
        yield tmp_path


def test_legacy_assistant_gets_uuid_on_load(_tmp_assistants_dir):
    """Loading an assistant JSON without uuid assigns one and rewrites."""
    legacy = {"id": "old", "name": "Old", "model": "m", "system_prompt": "p"}
    (_tmp_assistants_dir / "old.json").write_text(json.dumps(legacy))
    loaded = assistants.get_assistant("old")
    assert loaded is not None
    assert "uuid" in loaded
    assert len(loaded["uuid"]) == 32
    # Verify it was written back
    on_disk = json.loads((_tmp_assistants_dir / "old.json").read_text())
    assert "uuid" in on_disk


def test_legacy_assistant_gets_version_1(_tmp_assistants_dir):
    legacy = {"id": "old", "name": "Old", "model": "m", "system_prompt": "p"}
    (_tmp_assistants_dir / "old.json").write_text(json.dumps(legacy))
    loaded = assistants.get_assistant("old")
    assert loaded["version"] == 1


def test_migration_is_idempotent(_tmp_assistants_dir):
    legacy = {"id": "old", "name": "Old", "model": "m", "system_prompt": "p"}
    (_tmp_assistants_dir / "old.json").write_text(json.dumps(legacy))
    first = assistants.get_assistant("old")
    second = assistants.get_assistant("old")
    assert first["uuid"] == second["uuid"]


def test_default_assistant_gets_uuid():
    default = assistants.get_assistant("default")
    assert default is not None
    assert "uuid" in default
    assert default["uuid"] == assistants._DEFAULT_UUID
