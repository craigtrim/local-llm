"""Tests for assistant version history snapshots (#29)."""

from unittest.mock import patch

import pytest

from local_llm import assistants


@pytest.fixture(autouse=True)
def _tmp_assistants_dir(tmp_path):
    with patch("local_llm.assistants.ASSISTANTS_DIR", str(tmp_path)):
        yield tmp_path


def _make(name="Test", model="m", prompt="p", **kw):
    return assistants.save_assistant({"name": name, "model": model, "system_prompt": prompt, **kw})


def test_version_snapshot_saved_on_edit(_tmp_assistants_dir):
    first = _make(name="Snap")
    uid = first["uuid"]
    assistants.save_assistant({"id": "snap", "name": "Snap", "model": "m", "system_prompt": "v2"})
    history_dir = _tmp_assistants_dir / "history"
    assert (history_dir / f"{uid}_v1.json").exists()


def test_version_snapshot_content_matches_pre_edit():
    first = _make(name="Content")
    uid = first["uuid"]
    assistants.save_assistant({"id": "content", "name": "Content", "model": "m", "system_prompt": "updated"})
    snapshot = assistants.get_version(uid, 1)
    assert snapshot is not None
    assert snapshot["system_prompt"] == "p"  # original prompt, not "updated"


def test_list_versions():
    first = _make(name="Multi")
    uid = first["uuid"]
    assistants.save_assistant({"id": "multi", "name": "Multi", "model": "m", "system_prompt": "v2"})
    assistants.save_assistant({"id": "multi", "name": "Multi", "model": "m", "system_prompt": "v3"})
    versions = assistants.list_versions(uid)
    assert versions == [1, 2]


def test_get_version():
    first = _make(name="Get")
    uid = first["uuid"]
    assistants.save_assistant({"id": "get", "name": "Get", "model": "m", "system_prompt": "second"})
    v1 = assistants.get_version(uid, 1)
    assert v1["system_prompt"] == "p"


def test_delete_assistant_preserves_history(_tmp_assistants_dir):
    first = _make(name="Deletable")
    uid = first["uuid"]
    assistants.save_assistant({"id": "deletable", "name": "Deletable", "model": "m", "system_prompt": "v2"})
    assistants.delete_assistant("deletable")
    # History files should still exist
    assert assistants.list_versions(uid) == [1]


def test_history_dir_created_on_first_edit(_tmp_assistants_dir):
    history_dir = _tmp_assistants_dir / "history"
    assert not history_dir.exists()
    first = _make(name="Lazy")
    # No history yet (first save, no snapshot needed)
    assert not history_dir.exists()
    # Edit triggers snapshot
    assistants.save_assistant({"id": "lazy", "name": "Lazy", "model": "m", "system_prompt": "v2"})
    assert history_dir.exists()
