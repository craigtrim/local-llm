"""Tests for greeting regeneration on assistant edit (#40)."""

import json
from unittest.mock import patch, call

import pytest

from local_llm import assistants


@pytest.fixture(autouse=True)
def _tmp_assistants_dir(tmp_path):
    with patch("local_llm.assistants.ASSISTANTS_DIR", str(tmp_path)):
        yield tmp_path


_call_count = 0


def _greeting_fn(name, system_prompt, model):
    global _call_count
    _call_count += 1
    return [f"{name}-{system_prompt[:10]}-{_call_count}-{i}" for i in range(10)]


@pytest.fixture(autouse=True)
def _reset_counter():
    global _call_count
    _call_count = 0


def _make(name="Test", model="m", prompt="p", **kw):
    return assistants.save_assistant(
        {"name": name, "model": model, "system_prompt": prompt, **kw},
        generate_greetings_fn=_greeting_fn,
    )


def test_change_system_prompt_regenerates():
    first = _make(name="Bot", prompt="old prompt")
    old_greetings = first["greetings"]
    second = assistants.save_assistant(
        {"id": "bot", "name": "Bot", "model": "m", "system_prompt": "new prompt"},
        generate_greetings_fn=_greeting_fn,
    )
    assert second["greetings"] != old_greetings


def test_change_model_regenerates():
    first = _make(name="Bot2", model="m1")
    old_greetings = first["greetings"]
    second = assistants.save_assistant(
        {"id": "bot2", "name": "Bot2", "model": "m2", "system_prompt": "p"},
        generate_greetings_fn=_greeting_fn,
    )
    assert second["greetings"] != old_greetings


def test_change_name_regenerates():
    first = _make(name="OldName")
    old_greetings = first["greetings"]
    second = assistants.save_assistant(
        {"id": "oldname", "name": "NewName", "model": "m", "system_prompt": "p"},
        generate_greetings_fn=_greeting_fn,
    )
    assert second["greetings"] != old_greetings


def test_change_all_three_regenerates():
    first = _make(name="A", model="m1", prompt="p1")
    old_greetings = first["greetings"]
    second = assistants.save_assistant(
        {"id": "a", "name": "B", "model": "m2", "system_prompt": "p2"},
        generate_greetings_fn=_greeting_fn,
    )
    assert second["greetings"] != old_greetings


def test_change_color_preserves_greetings():
    first = _make(name="ColorBot")
    old_greetings = first["greetings"]
    second = assistants.save_assistant(
        {"id": "colorbot", "name": "ColorBot", "model": "m", "system_prompt": "p",
         "avatar_color": "#ff0000"},
        generate_greetings_fn=_greeting_fn,
    )
    assert second["greetings"] == old_greetings


def test_change_description_preserves_greetings():
    first = _make(name="DescBot")
    old_greetings = first["greetings"]
    second = assistants.save_assistant(
        {"id": "descbot", "name": "DescBot", "model": "m", "system_prompt": "p",
         "description": "new description"},
        generate_greetings_fn=_greeting_fn,
    )
    assert second["greetings"] == old_greetings


def test_change_context_tokens_preserves_greetings():
    first = _make(name="CtxBot")
    old_greetings = first["greetings"]
    second = assistants.save_assistant(
        {"id": "ctxbot", "name": "CtxBot", "model": "m", "system_prompt": "p",
         "context_tokens": 8192},
        generate_greetings_fn=_greeting_fn,
    )
    assert second["greetings"] == old_greetings


def test_change_token_ratio_preserves_greetings():
    first = _make(name="RatioBot")
    old_greetings = first["greetings"]
    second = assistants.save_assistant(
        {"id": "ratiobot", "name": "RatioBot", "model": "m", "system_prompt": "p",
         "token_estimate_ratio": 3.5},
        generate_greetings_fn=_greeting_fn,
    )
    assert second["greetings"] == old_greetings


def test_change_context_reserve_preserves_greetings():
    first = _make(name="ResBot")
    old_greetings = first["greetings"]
    second = assistants.save_assistant(
        {"id": "resbot", "name": "ResBot", "model": "m", "system_prompt": "p",
         "context_reserve": 1024},
        generate_greetings_fn=_greeting_fn,
    )
    assert second["greetings"] == old_greetings


def test_change_color_and_prompt_regenerates():
    first = _make(name="MixBot")
    old_greetings = first["greetings"]
    second = assistants.save_assistant(
        {"id": "mixbot", "name": "MixBot", "model": "m", "system_prompt": "different",
         "avatar_color": "#00ff00"},
        generate_greetings_fn=_greeting_fn,
    )
    assert second["greetings"] != old_greetings
