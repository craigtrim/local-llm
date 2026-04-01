import json
from pathlib import Path

import pytest

from local_llm.obsidian import _format_callout, convert


@pytest.fixture
def archive_path(tmp_path):
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
    ]
    path = tmp_path / "20260401_142307.json"
    path.write_text(json.dumps(messages))
    return path


@pytest.fixture
def vault_dir(tmp_path):
    return tmp_path / "vault"


def test_convert_produces_correct_markdown(archive_path, vault_dir):
    result = convert(archive_path, str(vault_dir), "llama3.2:1b")

    assert result is not None
    assert result.exists()
    assert result.name == "Chat 20260401_142307.md"

    text = result.read_text()
    assert "date: 2026-04-01T14:23:07Z" in text
    assert "model: llama3.2:1b" in text
    assert "# Chat — 2026-04-01 14:23" in text
    assert "> [!user]" in text
    assert "> Hello" in text
    assert "> [!assistant]" in text
    assert "> Hi there!" in text


def test_convert_without_model(archive_path, vault_dir):
    result = convert(archive_path, str(vault_dir))

    text = result.read_text()
    assert "model:" not in text
    assert "date: 2026-04-01T14:23:07Z" in text


def test_convert_skips_system_messages(archive_path, vault_dir):
    result = convert(archive_path, str(vault_dir))

    text = result.read_text()
    assert "You are a helpful assistant." not in text
    assert "[!system]" not in text


def test_convert_multiline_content(tmp_path, vault_dir):
    messages = [
        {"role": "user", "content": "Tell me a story"},
        {"role": "assistant", "content": "Once upon a time.\n\nThe end."},
    ]
    path = tmp_path / "20260401_150000.json"
    path.write_text(json.dumps(messages))

    result = convert(path, str(vault_dir))
    text = result.read_text()

    assert "> Once upon a time." in text
    assert "\n>\n" in text
    assert "> The end." in text


def test_convert_returns_none_on_bad_input(tmp_path, vault_dir):
    bad_path = tmp_path / "nonexistent.json"
    result = convert(bad_path, str(vault_dir))
    assert result is None


def test_convert_creates_vault_dir(archive_path, tmp_path):
    nested = tmp_path / "a" / "b" / "c"
    result = convert(archive_path, str(nested))

    assert result is not None
    assert nested.exists()


def test_convert_includes_tags(archive_path, vault_dir):
    result = convert(archive_path, str(vault_dir))

    text = result.read_text()
    assert "tags:" in text
    assert "  - local-llm" in text
    assert "  - chat-archive" in text


def test_format_callout_basic():
    result = _format_callout("user", "Hello world")
    assert result == "> [!user]\n> Hello world"


def test_format_callout_empty_lines():
    result = _format_callout("assistant", "Line one\n\nLine two")
    assert result == "> [!assistant]\n> Line one\n>\n> Line two"
