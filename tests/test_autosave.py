"""Tests for auto-save behavior (#47)."""

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
        from local_llm.api import app, sessions, session_meta
        sessions.clear()
        session_meta.clear()
        yield TestClient(app), tmp_path / "archives"


def _create_assistant(client):
    resp = client.post("/api/assistants", json={
        "name": "TestBot", "model": "m", "system_prompt": "You help."
    })
    return resp.json()


def test_autosave_after_user_message(_isolated_env):
    """After a user sends a message, an archive should exist."""
    client, archive_dir = _isolated_env
    assistant = _create_assistant(client)
    resp = client.post("/api/sessions", json={"assistant_id": assistant["id"]})
    sid = resp.json()["session_id"]

    from local_llm.api import sessions, _autosave
    sessions[sid].history.add("user", "hello")
    _autosave(sid)

    files = list(archive_dir.glob("*.json"))
    assert len(files) == 1
    data = json.loads(files[0].read_text())
    user_msgs = [m for m in data["messages"] if m["role"] == "user"]
    assert len(user_msgs) == 1


def test_autosave_after_assistant_response(_isolated_env):
    """After assistant responds, archive has both user and assistant messages."""
    client, archive_dir = _isolated_env
    assistant = _create_assistant(client)
    resp = client.post("/api/sessions", json={"assistant_id": assistant["id"]})
    sid = resp.json()["session_id"]

    from local_llm.api import sessions, _autosave
    sessions[sid].history.add("user", "hello")
    _autosave(sid)
    sessions[sid].history.add("assistant", "hi there")
    _autosave(sid)

    files = list(archive_dir.glob("*.json"))
    assert len(files) == 1, f"Expected 1 file, got {len(files)}"
    data = json.loads(files[0].read_text())
    assert len([m for m in data["messages"] if m["role"] == "user"]) == 1
    assert len([m for m in data["messages"] if m["role"] == "assistant"]) == 1


def test_autosave_overwrites_same_file(_isolated_env):
    """Multiple exchanges produce one archive file, not many."""
    client, archive_dir = _isolated_env
    assistant = _create_assistant(client)
    resp = client.post("/api/sessions", json={"assistant_id": assistant["id"]})
    sid = resp.json()["session_id"]

    from local_llm.api import sessions, _autosave
    for i in range(3):
        sessions[sid].history.add("user", f"q{i}")
        _autosave(sid)
        sessions[sid].history.add("assistant", f"a{i}")
        _autosave(sid)

    files = list(archive_dir.glob("*.json"))
    assert len(files) == 1
    data = json.loads(files[0].read_text())
    assert len([m for m in data["messages"] if m["role"] == "user"]) == 3


def test_resumed_session_overwrites_source(_isolated_env):
    """Resuming an archive and chatting overwrites the original file."""
    client, archive_dir = _isolated_env
    assistant = _create_assistant(client)

    # Create initial archive
    resp = client.post("/api/sessions", json={"assistant_id": assistant["id"]})
    sid = resp.json()["session_id"]
    from local_llm.api import sessions, _autosave
    sessions[sid].history.add("user", "original question")
    sessions[sid].history.add("assistant", "original answer")
    _autosave(sid)

    files_before = list(archive_dir.glob("*.json"))
    assert len(files_before) == 1
    filename = files_before[0].name

    # Resume and add a message
    resume_resp = client.post("/api/sessions/resume", json={
        "filename": filename, "model": "m", "assistant_id": assistant["id"],
    })
    new_sid = resume_resp.json()["session_id"]
    sessions[new_sid].history.add("user", "follow up")
    _autosave(new_sid)

    # Should still be one file
    files_after = list(archive_dir.glob("*.json"))
    assert len(files_after) == 1
    assert files_after[0].name == filename

    data = json.loads(files_after[0].read_text())
    user_msgs = [m for m in data["messages"] if m["role"] == "user"]
    assert len(user_msgs) == 2  # original + follow up


def test_new_session_creates_new_archive(_isolated_env):
    """A fresh session (not resumed) creates a new archive file."""
    client, archive_dir = _isolated_env
    assistant = _create_assistant(client)

    # First session
    resp1 = client.post("/api/sessions", json={"assistant_id": assistant["id"]})
    sid1 = resp1.json()["session_id"]
    from local_llm.api import sessions, _autosave
    sessions[sid1].history.add("user", "q1")
    _autosave(sid1)

    # Second session
    resp2 = client.post("/api/sessions", json={"assistant_id": assistant["id"]})
    sid2 = resp2.json()["session_id"]
    sessions[sid2].history.add("user", "q2")
    _autosave(sid2)

    files = list(archive_dir.glob("*.json"))
    assert len(files) == 2
