"""Tests for archive overwrite behavior (#47)."""

import json
from unittest.mock import patch

import pytest

from local_llm import archive


@pytest.fixture(autouse=True)
def _tmp_archive_dir(tmp_path):
    with patch("local_llm.archive.ARCHIVE_DIR", str(tmp_path)):
        yield tmp_path


def _sample_messages():
    return [
        {"role": "system", "content": "You are helpful.", "timestamp": "2026-04-01T12:00:00+00:00"},
        {"role": "user", "content": "Hello", "timestamp": "2026-04-01T12:00:01+00:00"},
        {"role": "assistant", "content": "Hi there", "timestamp": "2026-04-01T12:00:02+00:00"},
    ]


def test_save_with_overwrite_path(_tmp_archive_dir):
    """Passing overwrite_path writes to that file, not a new one."""
    # Create an initial archive
    path = archive.save(_sample_messages(), title="original", model="m")
    filename = path.name
    file_count_before = len(list(_tmp_archive_dir.glob("*.json")))

    # Overwrite it
    msgs = _sample_messages() + [
        {"role": "user", "content": "follow up", "timestamp": "2026-04-01T12:01:00+00:00"},
    ]
    archive.save(msgs, title="updated", model="m", overwrite_path=filename)

    file_count_after = len(list(_tmp_archive_dir.glob("*.json")))
    assert file_count_after == file_count_before, "Overwrite created a new file"


def test_save_without_overwrite_creates_new(_tmp_archive_dir):
    """Without overwrite_path, a new file is created."""
    archive.save(_sample_messages(), title="first", model="m")
    archive.save(_sample_messages(), title="second", model="m")
    files = list(_tmp_archive_dir.glob("*.json"))
    assert len(files) == 2


def test_overwrite_updates_content(_tmp_archive_dir):
    """Overwriting updates the file content."""
    path = archive.save(_sample_messages(), title="original", model="m")
    filename = path.name

    new_msgs = _sample_messages() + [
        {"role": "user", "content": "new question", "timestamp": "2026-04-01T12:01:00+00:00"},
        {"role": "assistant", "content": "new answer", "timestamp": "2026-04-01T12:01:01+00:00"},
    ]
    archive.save(new_msgs, title="updated", model="m", overwrite_path=filename)

    data = json.loads(path.read_text())
    assert len(data["messages"]) == 5
    assert data["title"] == "updated"


def test_overwrite_preserves_filename(_tmp_archive_dir):
    """The filename stays exactly the same after overwrite."""
    path = archive.save(_sample_messages(), title="original", model="m")
    filename = path.name

    result = archive.save(_sample_messages(), title="changed title", model="m", overwrite_path=filename)
    assert result.name == filename
