"""Tests for per-message assistant metadata in archives (#30)."""

import json
from unittest.mock import patch

import pytest

from local_llm import archive
from local_llm.history import ConversationHistory


@pytest.fixture(autouse=True)
def _tmp_archive_dir(tmp_path):
    with patch("local_llm.archive.ARCHIVE_DIR", str(tmp_path)):
        yield tmp_path


def test_archive_round_trip_with_per_message_uuid():
    """Messages with assistant_uuid survive save/load."""
    h = ConversationHistory(context_limit=4096, assistant_uuid="aaa111bbb222ccc333ddd444eee555ff", assistant_name="Bot")
    h.add("user", "hi")
    h.add("assistant", "hello")
    path = archive.save(h.messages, title="per-msg", model="m")
    data = archive.load_archive(path.name)
    assistant_msgs = [m for m in data["messages"] if m["role"] == "assistant"]
    assert assistant_msgs[0]["assistant_uuid"] == "aaa111bbb222ccc333ddd444eee555ff"
    assert assistant_msgs[0]["assistant_name"] == "Bot"


def test_archive_validates_with_per_message_metadata():
    """validate_archive accepts messages with extra assistant fields."""
    data = {
        "title": "test",
        "created_at": "2026-04-01T12:00:00+00:00",
        "archived_at": "2026-04-01T12:00:00+00:00",
        "model": "m",
        "client_ip": None,
        "user_agent": None,
        "messages": [
            {"role": "user", "content": "hi", "timestamp": "2026-04-01T12:00:00+00:00"},
            {"role": "assistant", "content": "hello", "timestamp": "2026-04-01T12:00:01+00:00",
             "assistant_uuid": "abc", "assistant_name": "Bot"},
        ],
    }
    errors = archive.validate_archive(data)
    assert errors == []


def test_archive_validates_without_per_message_metadata():
    """validate_archive accepts messages without assistant fields."""
    data = {
        "title": "test",
        "created_at": "2026-04-01T12:00:00+00:00",
        "archived_at": "2026-04-01T12:00:00+00:00",
        "model": "m",
        "client_ip": None,
        "user_agent": None,
        "messages": [
            {"role": "user", "content": "hi", "timestamp": "2026-04-01T12:00:00+00:00"},
            {"role": "assistant", "content": "hello", "timestamp": "2026-04-01T12:00:01+00:00"},
        ],
    }
    errors = archive.validate_archive(data)
    assert errors == []


def test_mixed_messages_with_and_without_uuid():
    """History with assistant change mid-conversation."""
    h = ConversationHistory(context_limit=4096, assistant_uuid="aaa111bbb222ccc333ddd444eee555ff", assistant_name="Bot1")
    h.add("user", "q1")
    h.add("assistant", "a1")
    msgs = h.messages
    # Simulate a second assistant's message added without uuid
    msgs.append({"role": "assistant", "content": "a2", "timestamp": "2026-04-01T12:00:00+00:00"})
    path = archive.save(msgs, title="mixed", model="m")
    data = archive.load_archive(path.name)
    assert data["messages"][1].get("assistant_uuid") == "aaa111bbb222ccc333ddd444eee555ff"
    assert "assistant_uuid" not in data["messages"][2]


def test_user_messages_never_have_uuid_in_archive():
    h = ConversationHistory(context_limit=4096, assistant_uuid="aaa111bbb222ccc333ddd444eee555ff", assistant_name="Bot")
    h.add("user", "hi")
    h.add("assistant", "hello")
    h.add("user", "bye")
    path = archive.save(h.messages, title="check-user", model="m")
    data = archive.load_archive(path.name)
    user_msgs = [m for m in data["messages"] if m["role"] == "user"]
    for m in user_msgs:
        assert "assistant_uuid" not in m
