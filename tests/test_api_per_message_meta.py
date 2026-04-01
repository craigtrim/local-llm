"""Tests for per-message assistant metadata in API sessions (#30)."""

import tempfile
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path):
    tmp_assistants = str(tmp_path / "assistants")
    tmp_archives = str(tmp_path / "archives")

    with (
        patch("ollama.chat", return_value={"message": {"content": "reply"}}),
        patch("ollama.list", return_value=type("R", (), {"models": [type("M", (), {"model": "m"})()]})()),
        patch("ollama.show", return_value={"model_info": {"llama.context_length": 4096}}),
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


def test_session_messages_tagged_with_uuid(_isolated_env):
    client = _isolated_env
    assistant = _create_assistant(client)
    resp = client.post("/api/sessions", json={"assistant_id": assistant["id"]})
    sid = resp.json()["session_id"]
    assert resp.json().get("assistant_uuid") == assistant["uuid"]

    # Add a message via the history directly (WebSocket would do this)
    from local_llm.api import sessions
    info = sessions[sid]
    info.history.add("user", "hi")
    info.history.add("assistant", "hello")

    msgs = info.history.messages
    assistant_msg = [m for m in msgs if m["role"] == "assistant"][0]
    assert assistant_msg["assistant_uuid"] == assistant["uuid"]
    assert assistant_msg["assistant_name"] == assistant["name"]


def test_session_without_assistant_no_uuid(_isolated_env):
    client = _isolated_env
    resp = client.post("/api/sessions", json={"model": "m"})
    sid = resp.json()["session_id"]

    from local_llm.api import sessions
    info = sessions[sid]
    info.history.add("assistant", "hello")

    msgs = info.history.messages
    assistant_msg = [m for m in msgs if m["role"] == "assistant"][0]
    assert "assistant_uuid" not in assistant_msg


def test_clear_preserves_assistant_uuid(_isolated_env):
    client = _isolated_env
    assistant = _create_assistant(client)
    resp = client.post("/api/sessions", json={"assistant_id": assistant["id"]})
    sid = resp.json()["session_id"]
    clear_resp = client.post(f"/api/sessions/{sid}/clear")
    new_sid = clear_resp.json()["session_id"]

    from local_llm.api import sessions
    new_info = sessions[new_sid]
    assert new_info.assistant_uuid == assistant["uuid"]


def test_resume_preserves_uuid(_isolated_env):
    client = _isolated_env
    assistant = _create_assistant(client)
    # Create and clear to produce an archive
    resp = client.post("/api/sessions", json={"assistant_id": assistant["id"]})
    sid = resp.json()["session_id"]
    from local_llm.api import sessions
    sessions[sid].history.add("user", "q")
    sessions[sid].history.add("assistant", "a")
    client.post(f"/api/sessions/{sid}/clear")

    # Get the archive
    archives = client.get("/api/archives").json()["archives"]
    assert len(archives) >= 1
    filename = archives[0]["filename"]

    # Resume
    resume_resp = client.post("/api/sessions/resume", json={
        "filename": filename, "model": "m",
        "assistant_id": assistant["id"],
    })
    assert resume_resp.json().get("assistant_uuid") == assistant["uuid"]
