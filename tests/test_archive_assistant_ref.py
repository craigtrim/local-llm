"""Tests for archive assistant UUID references (#29)."""

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


def test_save_stores_assistant_uuid():
    path = archive.save(
        _sample_messages(), title="test",
        assistant_uuid="abc123def456abc123def456abc123de",
        assistant_version=3,
        model="m",
    )
    data = json.loads(path.read_text())
    assert data["assistant_uuid"] == "abc123def456abc123def456abc123de"
    assert data["assistant_version"] == 3


def test_save_without_uuid():
    path = archive.save(_sample_messages(), title="no uuid", model="m")
    data = json.loads(path.read_text())
    assert data["assistant_uuid"] is None
    assert data["assistant_version"] is None


def test_list_archives_includes_uuid(_tmp_archive_dir):
    archive.save(
        _sample_messages(), title="listed",
        assistant_uuid="abc123def456abc123def456abc123de",
        model="m",
    )
    items = archive.list_archives()
    assert len(items) == 1
    assert items[0]["assistant_uuid"] == "abc123def456abc123def456abc123de"


def test_load_archive_includes_uuid():
    path = archive.save(
        _sample_messages(), title="loadable",
        assistant_uuid="abc123def456abc123def456abc123de",
        assistant_version=2,
        model="m",
    )
    data = archive.load_archive(path.name)
    assert data["assistant_uuid"] == "abc123def456abc123def456abc123de"
    assert data["assistant_version"] == 2


def test_archive_round_trip_with_assistant_metadata():
    path = archive.save(
        _sample_messages(), title="round trip",
        assistant_id="my-bot", assistant_name="My Bot",
        assistant_uuid="abc123def456abc123def456abc123de",
        assistant_version=1,
        model="m",
    )
    data = archive.load_archive(path.name)
    assert data["assistant_id"] == "my-bot"
    assert data["assistant_name"] == "My Bot"
    assert data["assistant_uuid"] == "abc123def456abc123def456abc123de"
    assert data["assistant_version"] == 1
