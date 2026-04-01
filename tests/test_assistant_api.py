"""Unit tests for assistant API endpoints."""

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _patch_ollama():
    """Patch ollama before importing any local_llm modules."""
    with (
        patch("ollama.chat", return_value={"message": {"content": "ok"}}),
        patch("ollama.list", return_value=type("R", (), {"models": []})()),
        patch("ollama.show", return_value={"model_info": {"llama.context_length": 4096}}),
    ):
        yield


@pytest.fixture(autouse=True)
def _tmp_dirs(tmp_path):
    """Isolate assistant and archive storage to temp directories."""
    with (
        patch("local_llm.assistants.ASSISTANTS_DIR", str(tmp_path / "assistants")),
        patch("local_llm.archive.ARCHIVE_DIR", str(tmp_path / "archives")),
    ):
        yield


@pytest.fixture()
def client():
    from local_llm.api import app, sessions
    from fastapi.testclient import TestClient

    sessions.clear()
    with TestClient(app) as c:
        yield c
    sessions.clear()


# --- CRUD endpoints ---


def test_list_assistants_returns_default(client):
    res = client.get("/api/assistants")
    assert res.status_code == 200
    data = res.json()
    assert len(data["assistants"]) >= 1
    assert data["assistants"][0]["id"] == "default"


def test_create_assistant(client):
    res = client.post("/api/assistants", json={
        "name": "Code Helper",
        "model": "test-model",
        "system_prompt": "You help with code.",
    })
    assert res.status_code == 200
    assert res.json()["id"] == "code-helper"

    # Should appear in list
    listing = client.get("/api/assistants").json()
    ids = [a["id"] for a in listing["assistants"]]
    assert "code-helper" in ids


def test_create_assistant_validation(client):
    res = client.post("/api/assistants", json={
        "name": "",
        "system_prompt": "x",
    })
    assert res.status_code == 400  # empty name caught by assistants.save_assistant


def test_update_assistant(client):
    client.post("/api/assistants", json={
        "name": "Original",
        "model": "m",
        "system_prompt": "old prompt",
    })
    res = client.put("/api/assistants/original", json={
        "name": "Original",
        "model": "m",
        "system_prompt": "new prompt",
    })
    assert res.status_code == 200
    loaded = client.get("/api/assistants").json()
    assistant = next(a for a in loaded["assistants"] if a["id"] == "original")
    assert assistant["system_prompt"] == "new prompt"


def test_update_nonexistent_returns_404(client):
    res = client.put("/api/assistants/nonexistent", json={
        "name": "X",
        "model": "m",
        "system_prompt": "x",
    })
    assert res.status_code == 404


def test_delete_assistant_endpoint(client):
    client.post("/api/assistants", json={
        "name": "Temporary",
        "model": "m",
        "system_prompt": "x",
    })
    res = client.delete("/api/assistants/temporary")
    assert res.status_code == 200
    assert res.json()["deleted"] == "temporary"

    listing = client.get("/api/assistants").json()
    ids = [a["id"] for a in listing["assistants"]]
    assert "temporary" not in ids


def test_delete_default_returns_400(client):
    res = client.delete("/api/assistants/default")
    assert res.status_code == 400


def test_delete_nonexistent_returns_404(client):
    res = client.delete("/api/assistants/nope")
    assert res.status_code == 404


# --- Session creation with assistant ---


def test_create_session_with_assistant(client):
    client.post("/api/assistants", json={
        "name": "Tester",
        "model": "test-model",
        "system_prompt": "You are a tester.",
        "avatar_color": "#c94040",
    })
    res = client.post("/api/sessions", json={"assistant_id": "tester"})
    assert res.status_code == 200
    data = res.json()
    assert data["assistant_id"] == "tester"
    assert data["assistant_name"] == "Tester"
    assert data["assistant_color"] == "#c94040"
    assert data["model"] == "test-model"


def test_create_session_with_assistant_uses_custom_prompt(client):
    client.post("/api/assistants", json={
        "name": "Custom Prompt",
        "model": "test-model",
        "system_prompt": "UNIQUE_PROMPT_MARKER",
    })
    res = client.post("/api/sessions", json={"assistant_id": "custom-prompt"})
    data = res.json()
    sid = data["session_id"]

    from local_llm.api import sessions
    info = sessions[sid]
    system_msgs = [m for m in info.history.messages if m["role"] == "system"]
    assert any("UNIQUE_PROMPT_MARKER" in m["content"] for m in system_msgs)


def test_create_session_with_nonexistent_assistant(client):
    res = client.post("/api/sessions", json={"assistant_id": "no-such"})
    assert res.status_code == 404


def test_create_session_backward_compat_model_only(client):
    """Old-style session creation with just model still works."""
    res = client.post("/api/sessions", json={"model": "test-model"})
    assert res.status_code == 200
    data = res.json()
    assert data["assistant_id"] is None
    assert data["model"] == "test-model"


# --- Status includes assistant info ---


def test_status_includes_assistant_info(client):
    client.post("/api/assistants", json={
        "name": "Status Test",
        "model": "test-model",
        "system_prompt": "x",
    })
    session = client.post("/api/sessions", json={"assistant_id": "status-test"}).json()
    res = client.get(f"/api/sessions/{session['session_id']}/status")
    assert res.status_code == 200
    data = res.json()
    assert data["assistant_id"] == "status-test"
    assert data["assistant_name"] == "Status Test"


# --- Clear preserves assistant ---


def test_clear_preserves_assistant(client):
    client.post("/api/assistants", json={
        "name": "Persistent",
        "model": "test-model",
        "system_prompt": "persist me",
    })
    session = client.post("/api/sessions", json={"assistant_id": "persistent"}).json()
    clear_res = client.post(f"/api/sessions/{session['session_id']}/clear")
    assert clear_res.status_code == 200

    new_sid = clear_res.json()["session_id"]
    from local_llm.api import sessions
    info = sessions[new_sid]
    assert info.assistant_id == "persistent"
    assert info.assistant_name == "Persistent"
