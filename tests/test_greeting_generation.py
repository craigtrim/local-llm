"""Tests for greeting generation and parsing (#40, #53)."""

import json
from unittest.mock import patch

import pytest

from local_llm import client
from local_llm.client import _parse_greetings


# --- Parser unit tests (#53) ---


def test_parse_clean_lines():
    raw = "Hello there!\nWelcome aboard.\nHi, how can I help?"
    result = _parse_greetings(raw)
    assert result == ["Hello there!", "Welcome aboard.", "Hi, how can I help?"]


def test_parse_strips_numbering():
    raw = "1. Hello\n2. Welcome\n3. Hi there"
    result = _parse_greetings(raw)
    assert result == ["Hello", "Welcome", "Hi there"]


def test_parse_strips_parenthetical_numbering():
    raw = "1) Hello\n2) Welcome"
    result = _parse_greetings(raw)
    assert result == ["Hello", "Welcome"]


def test_parse_strips_bullets():
    raw = "- Hello\n- Welcome\n* Hi there"
    result = _parse_greetings(raw)
    assert result == ["Hello", "Welcome", "Hi there"]


def test_parse_strips_quotes():
    raw = '"Hello there!"\n\'Welcome aboard.\''
    result = _parse_greetings(raw)
    assert result == ["Hello there!", "Welcome aboard."]


def test_parse_skips_blank_lines():
    raw = "Hello\n\n\nWelcome\n   \nHi"
    result = _parse_greetings(raw)
    assert result == ["Hello", "Welcome", "Hi"]


def test_parse_truncated_output():
    """Truncated last line should still return the complete lines."""
    raw = "Hello there!\nWelcome aboard.\nHi, I'm here to he"
    result = _parse_greetings(raw)
    assert len(result) == 3
    assert result[0] == "Hello there!"


def test_parse_empty_input():
    assert _parse_greetings("") == []
    assert _parse_greetings("   \n  \n") == []


# --- generate_greetings integration tests ---


def _fake_chat_lines(model, messages):
    """Return newline-delimited greetings."""
    return "\n".join(f"Hello greeting {i}!" for i in range(8))


@patch("local_llm.client.chat", side_effect=_fake_chat_lines)
def test_generate_greetings_returns_expected_count(mock_chat):
    result = client.generate_greetings("Bot", "You help.", "m")
    assert 1 <= len(result) <= 10


@patch("local_llm.client.chat", side_effect=_fake_chat_lines)
def test_greetings_are_nonempty(mock_chat):
    result = client.generate_greetings("Bot", "You help.", "m")
    for g in result:
        assert g.strip(), f"Empty greeting found: {g!r}"


@patch("local_llm.client.chat", side_effect=_fake_chat_lines)
def test_greetings_are_unique(mock_chat):
    result = client.generate_greetings("Bot", "You help.", "m")
    assert len(set(result)) == len(result), "Duplicate greetings found"


@patch("local_llm.client.chat", return_value="not valid at all\x00\x01")
def test_bad_output_returns_something(mock_chat):
    """Even garbage input should not crash."""
    result = client.generate_greetings("Bot", "You help.", "m")
    assert isinstance(result, list)


@patch("local_llm.client.chat", side_effect=Exception("connection refused"))
def test_exception_returns_empty(mock_chat):
    result = client.generate_greetings("Bot", "You help.", "m")
    assert result == []


# --- Stress tests: 25 varied outputs to prove deterministic parsing (#53) ---


_STRESS_OUTPUTS = [
    # Clean lines
    "Hi!\nHello!\nWelcome!",
    # Numbered
    "1. Hi!\n2. Hello!\n3. Welcome!",
    "1) Hi!\n2) Hello!\n3) Welcome!",
    # Bullets
    "- Hi!\n- Hello!\n- Welcome!",
    "* Hi!\n* Hello!\n* Welcome!",
    # Quoted
    '"Hi!"\n"Hello!"\n"Welcome!"',
    # Mixed formatting
    '1. "Hi!"\n2. "Hello!"\n- Welcome!',
    # Extra whitespace
    "  Hi!  \n  Hello!  \n  Welcome!  ",
    # Blank lines scattered
    "\nHi!\n\nHello!\n\nWelcome!\n",
    # Trailing newlines
    "Hi!\nHello!\nWelcome!\n\n\n",
    # Single greeting
    "Hi there!",
    # Many greetings (should clamp)
    "\n".join(f"Greeting {i}" for i in range(20)),
    # Markdown fenced (model wraps in code block)
    "```\nHi!\nHello!\n```",
    # With preamble text the model might add
    "Here are your greetings:\nHi!\nHello!\nWelcome!",
    # Numbered with periods and extra spaces
    "1.  Hi there! \n2.  Hello friend! \n3.  Welcome aboard! ",
    # Unicode
    "Hello! \U0001f44b\nWelcome! \u2728",
    # Very long greeting
    "x" * 200 + "\nShort one.",
    # Truncated mid-sentence (simulating token limit)
    "Hello there!\nWelcome to the chat.\nI am here to hel",
    # Empty (should return [])
    "",
    # Only whitespace
    "   \n   \n   ",
    # Tab-separated (should treat as one line each)
    "Hi!\tHow are you?\nWelcome!\tGlad to help.",
    # Semicolons in greeting
    "Hi; welcome!\nHello; glad to help!",
    # Parentheses in greeting
    "Hello (and welcome)!\nHi (glad to help)!",
    # With colons
    "Greetings: welcome aboard!\nHello: ready to assist!",
    # Just numbers and dots (edge case, should be stripped to empty)
    "1.\n2.\n3.",
]


@pytest.mark.parametrize("output", _STRESS_OUTPUTS, ids=[f"stress_{i}" for i in range(len(_STRESS_OUTPUTS))])
def test_parse_greetings_stress(output):
    """Parser must never crash, always return a list of strings (#53)."""
    result = _parse_greetings(output)
    assert isinstance(result, list)
    for g in result:
        assert isinstance(g, str)
        assert g == g.strip()


@pytest.mark.parametrize("output", _STRESS_OUTPUTS, ids=[f"gen_stress_{i}" for i in range(len(_STRESS_OUTPUTS))])
@patch("local_llm.client.chat")
def test_generate_greetings_stress(mock_chat, output):
    """Full generate_greetings must never crash, always return list (#53)."""
    mock_chat.return_value = output
    result = client.generate_greetings("Bot", "You help.", "m")
    assert isinstance(result, list)
    assert len(result) <= 10  # clamped to GREETING_COUNT
    for g in result:
        assert isinstance(g, str)
        assert g.strip()  # no empty strings
