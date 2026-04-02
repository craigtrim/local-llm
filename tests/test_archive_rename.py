"""Tests for archive rename (#41)."""

import json
from unittest.mock import patch

import pytest


@pytest.fixture()
def tmp_archive_dir(tmp_path):
    with patch("local_llm.archive.ARCHIVE_DIR", str(tmp_path)):
        yield tmp_path


def _create_archive(tmp_dir, title="Original Title"):
    from local_llm.archive import save

    messages = [
        {"role": "user", "content": "hi", "timestamp": "2026-04-01T12:00:05+00:00"},
        {"role": "assistant", "content": "hello", "timestamp": "2026-04-01T12:00:07+00:00"},
    ]
    path = save(messages, title=title, model="test-model")
    return path


def test_rename_archive_updates_title(tmp_archive_dir):
    from local_llm.archive import rename_archive

    path = _create_archive(tmp_archive_dir)
    assert rename_archive(path.name, "New Title")

    data = json.loads(path.read_text())
    assert data["title"] == "New Title"


def test_rename_archive_preserves_other_fields(tmp_archive_dir):
    from local_llm.archive import rename_archive

    path = _create_archive(tmp_archive_dir)
    original = json.loads(path.read_text())

    rename_archive(path.name, "New Title")
    updated = json.loads(path.read_text())

    assert updated["model"] == original["model"]
    assert updated["messages"] == original["messages"]
    assert updated["created_at"] == original["created_at"]


def test_rename_nonexistent_returns_false(tmp_archive_dir):
    from local_llm.archive import rename_archive

    assert not rename_archive("nonexistent.json", "Title")


def test_rename_archive_reflected_in_list(tmp_archive_dir):
    from local_llm.archive import list_archives, rename_archive

    path = _create_archive(tmp_archive_dir)
    rename_archive(path.name, "Renamed Chat")

    archives = list_archives()
    assert len(archives) == 1
    assert archives[0]["title"] == "Renamed Chat"
