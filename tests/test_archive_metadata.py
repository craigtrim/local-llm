"""Tests for archive metadata (timestamps, IP, user-agent, model)."""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture()
def tmp_archive_dir(tmp_path):
    with patch("local_llm.archive.ARCHIVE_DIR", str(tmp_path)):
        yield tmp_path


def test_archive_save_includes_all_metadata(tmp_archive_dir):
    from local_llm.archive import save

    messages = [
        {"role": "system", "content": "You are helpful.", "timestamp": "2026-04-01T12:00:00+00:00"},
        {"role": "user", "content": "hi", "timestamp": "2026-04-01T12:00:05+00:00"},
        {"role": "assistant", "content": "hello", "timestamp": "2026-04-01T12:00:07+00:00"},
    ]
    path = save(
        messages,
        title="Test",
        model="qwen2.5:7b",
        client_ip="192.168.1.1",
        user_agent="Mozilla/5.0",
        created_at="2026-04-01T12:00:00+00:00",
    )
    assert path is not None

    data = json.loads(path.read_text())
    assert data["title"] == "Test"
    assert data["model"] == "qwen2.5:7b"
    assert data["client_ip"] == "192.168.1.1"
    assert data["user_agent"] == "Mozilla/5.0"
    assert data["created_at"] == "2026-04-01T12:00:00+00:00"
    assert "archived_at" in data
    assert data["archived_at"].startswith("2026")


def test_archive_save_defaults_model_to_unknown(tmp_archive_dir):
    from local_llm.archive import save

    messages = [
        {"role": "user", "content": "hi", "timestamp": "2026-04-01T12:00:05+00:00"},
        {"role": "assistant", "content": "hello", "timestamp": "2026-04-01T12:00:07+00:00"},
    ]
    path = save(messages)
    assert path is not None

    data = json.loads(path.read_text())
    assert data["model"] == "unknown"
    assert data["client_ip"] is None
    assert data["user_agent"] is None


def test_archive_save_generates_archived_at(tmp_archive_dir):
    from local_llm.archive import save

    messages = [
        {"role": "user", "content": "hi", "timestamp": "2026-04-01T12:00:05+00:00"},
        {"role": "assistant", "content": "hello", "timestamp": "2026-04-01T12:00:07+00:00"},
    ]
    path = save(messages, model="test")
    data = json.loads(path.read_text())

    # archived_at should be a valid ISO timestamp
    ts = datetime.fromisoformat(data["archived_at"])
    assert ts.tzinfo is not None


def test_message_has_timestamp():
    from local_llm.history import ConversationHistory

    history = ConversationHistory(context_limit=4096)
    history.add("user", "hello")

    msg = history.messages[0]
    assert "timestamp" in msg
    assert isinstance(msg["timestamp"], str)
    # Should be ISO-8601 with timezone
    ts = datetime.fromisoformat(msg["timestamp"])
    assert ts.tzinfo is not None


def test_timestamp_is_utc():
    from local_llm.history import ConversationHistory

    history = ConversationHistory(context_limit=4096)
    history.add("user", "hello")

    ts_str = history.messages[0]["timestamp"]
    ts = datetime.fromisoformat(ts_str)
    assert ts.utcoffset().total_seconds() == 0
