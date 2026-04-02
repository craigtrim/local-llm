"""Tests for greeting generation (#40)."""

import json
from unittest.mock import patch

import pytest

from local_llm import client


def _fake_chat(model, messages):
    """Return a JSON array of greetings."""
    return json.dumps([f"Hello {i}!" for i in range(20)])


@patch("local_llm.client.chat", side_effect=_fake_chat)
def test_generate_greetings_returns_20(mock_chat):
    result = client.generate_greetings("Bot", "You help.", "m")
    assert len(result) == 20


@patch("local_llm.client.chat", side_effect=_fake_chat)
def test_greetings_are_nonempty(mock_chat):
    result = client.generate_greetings("Bot", "You help.", "m")
    for g in result:
        assert g.strip(), f"Empty greeting found: {g!r}"


@patch("local_llm.client.chat", side_effect=_fake_chat)
def test_greetings_are_unique(mock_chat):
    result = client.generate_greetings("Bot", "You help.", "m")
    assert len(set(result)) == len(result), "Duplicate greetings found"


@patch("local_llm.client.chat", return_value='```json\n["Hi!", "Hello!"]\n```')
def test_handles_markdown_fenced_json(mock_chat):
    result = client.generate_greetings("Bot", "You help.", "m")
    assert result == ["Hi!", "Hello!"]


@patch("local_llm.client.chat", return_value="not json at all")
def test_bad_json_returns_empty(mock_chat):
    result = client.generate_greetings("Bot", "You help.", "m")
    assert result == []


@patch("local_llm.client.chat", side_effect=Exception("connection refused"))
def test_exception_returns_empty(mock_chat):
    result = client.generate_greetings("Bot", "You help.", "m")
    assert result == []
