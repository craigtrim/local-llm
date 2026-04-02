"""Tests for greeting API integration (#40)."""

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

FAKE_GREETINGS = [f"Hello {i}!" for i in range(20)]


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path):
    tmp_assistants = str(tmp_path / "assistants")
    tmp_archives = str(tmp_path / "archives")

    def _fake_chat(model, messages):
        text = messages[-1].get("content", "") if messages else ""
        if "unique greeting messages" in text:
            return json.dumps(FAKE_GREETINGS)
        return "test response"

    with (
        patch("ollama.chat", return_value={"message": {"content": "reply"}}),
        patch("ollama.list", return_value=type("R", (), {"models": [type("M", (), {"model": "m"})()]})()),
        patch("ollama.show", return_value={"model_info": {"llama.context_length": 4096}}),
        patch("local_llm.client.chat", side_effect=_fake_chat),
        patch("local_llm.assistants.ASSISTANTS_DIR", tmp_assistants),
        patch("local_llm.archive.ARCHIVE_DIR", tmp_archives),
    ):
        from local_llm.api import app, sessions
        sessions.clear()
        yield TestClient(app)


def _create_assistant(client, name="TestBot"):
    resp = client.post("/api/assistants", json={
        "name": name, "model": "m", "system_prompt": "You help."
    })
    return resp.json()


def test_create_session_returns_greeting(_isolated_env):
    client = _isolated_env
    assistant = _create_assistant(client)
    resp = client.post("/api/sessions", json={"assistant_id": assistant["id"]})
    data = resp.json()
    assert "greeting" in data
    assert data["greeting"] is not None
    assert data["greeting"] in FAKE_GREETINGS


def test_greeting_is_from_assistant(_isolated_env):
    client = _isolated_env
    assistant = _create_assistant(client)
    resp = client.post("/api/sessions", json={"assistant_id": assistant["id"]})
    assert resp.json()["greeting"] in assistant["greetings"]


def test_session_without_assistant_no_greeting(_isolated_env):
    client = _isolated_env
    resp = client.post("/api/sessions", json={"model": "m"})
    data = resp.json()
    assert data.get("greeting") is None


def test_greeting_not_in_history(_isolated_env):
    client = _isolated_env
    assistant = _create_assistant(client)
    resp = client.post("/api/sessions", json={"assistant_id": assistant["id"]})
    sid = resp.json()["session_id"]
    from local_llm.api import sessions
    info = sessions[sid]
    # Only the system message should be in history, not the greeting
    for msg in info.history.messages:
        assert msg["role"] != "assistant", "Greeting should not be in history"


def test_create_assistant_returns_greetings(_isolated_env):
    client = _isolated_env
    assistant = _create_assistant(client)
    assert "greetings" in assistant
    assert len(assistant["greetings"]) == 20


def test_update_prompt_returns_new_greetings(_isolated_env):
    client = _isolated_env
    assistant = _create_assistant(client, name="Updatable")
    old_greetings = assistant["greetings"]
    resp = client.put(f"/api/assistants/{assistant['id']}", json={
        "name": "Updatable", "model": "m", "system_prompt": "Completely different prompt"
    })
    new_greetings = resp.json()["greetings"]
    # Greetings should be regenerated (different call count = different content)
    assert "greetings" in resp.json()
    assert len(new_greetings) == 20


def test_update_color_preserves_greetings(_isolated_env):
    client = _isolated_env
    assistant = _create_assistant(client, name="ColorTest")
    old_greetings = assistant["greetings"]
    resp = client.put(f"/api/assistants/{assistant['id']}", json={
        "name": "ColorTest", "model": "m", "system_prompt": "You help.",
        "avatar_color": "#ff0000"
    })
    assert resp.json()["greetings"] == old_greetings


def test_greeting_rotates(_isolated_env):
    """Multiple sessions should not always get the same greeting."""
    client = _isolated_env
    assistant = _create_assistant(client)
    greetings_seen = set()
    for _ in range(10):
        resp = client.post("/api/sessions", json={"assistant_id": assistant["id"]})
        greetings_seen.add(resp.json()["greeting"])
    # With 20 options and 10 draws, extremely unlikely to get all the same
    assert len(greetings_seen) > 1, "All 10 sessions got the same greeting"
