"""Unit tests for the POST /api/sessions/resume endpoint."""

import json
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


@pytest.fixture()
def _tmp_archive_dir(tmp_path):
    """Point ARCHIVE_DIR to a temp directory for isolation."""
    with patch("local_llm.archive.ARCHIVE_DIR", str(tmp_path)):
        yield tmp_path


@pytest.fixture()
def test_archive(_tmp_archive_dir):
    """Create a well-formed archive file and return its filename."""
    data = {
        "title": "Code word test",
        "created_at": "2026-04-01T12:00:00+00:00",
        "archived_at": "2026-04-01T12:05:00+00:00",
        "model": "test-model",
        "client_ip": "127.0.0.1",
        "user_agent": "TestAgent/1.0",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant.", "timestamp": "2026-04-01T12:00:00+00:00"},
            {"role": "user", "content": "Remember the code word is banana.", "timestamp": "2026-04-01T12:00:05+00:00"},
            {"role": "assistant", "content": "Got it, the code word is banana.", "timestamp": "2026-04-01T12:00:07+00:00"},
        ],
    }
    path = _tmp_archive_dir / "20260401_120000_code-word-test.json"
    path.write_text(json.dumps(data))
    return path.name


@pytest.fixture()
def client(test_archive):
    """FastAPI test client with archive available."""
    from local_llm.api import app, sessions
    from fastapi.testclient import TestClient

    sessions.clear()
    with TestClient(app) as c:
        yield c
    sessions.clear()


def test_resume_creates_session_with_archived_messages(client, test_archive):
    res = client.post(
        "/api/sessions/resume",
        json={"model": "test-model", "filename": test_archive},
    )
    assert res.status_code == 200
    data = res.json()
    assert "session_id" in data
    assert data["messages_restored"] == 2  # user + assistant, system skipped

    # Verify the session has tokens used
    status = client.get(f"/api/sessions/{data['session_id']}/status")
    assert status.status_code == 200
    stats = status.json()
    assert stats["tokens_used"] > 0
    assert stats["qa_count"] == 1  # one user message


def test_resume_invalid_archive_returns_404(client):
    res = client.post(
        "/api/sessions/resume",
        json={"model": "test-model", "filename": "nonexistent.json"},
    )
    assert res.status_code == 404


def test_resume_no_model_returns_error(client):
    res = client.post(
        "/api/sessions/resume",
        json={"filename": "whatever.json"},
    )
    assert res.status_code == 404


def test_resume_preserves_current_system_prompt(client, test_archive):
    res = client.post(
        "/api/sessions/resume",
        json={"model": "test-model", "filename": test_archive},
    )
    data = res.json()
    sid = data["session_id"]

    from local_llm.api import sessions
    from local_llm.config import SYSTEM_PROMPT

    history = sessions[sid].history
    messages = history.messages
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == SYSTEM_PROMPT
    system_msgs = [m for m in messages if m["role"] == "system"]
    assert len(system_msgs) == 1


def test_resume_chat_has_context(client, test_archive):
    """After resume, the session history contains the archived user/assistant messages."""
    res = client.post(
        "/api/sessions/resume",
        json={"model": "test-model", "filename": test_archive},
    )
    data = res.json()
    sid = data["session_id"]

    from local_llm.api import sessions

    history = sessions[sid].history
    contents = [m["content"] for m in history.messages]
    assert any("banana" in c for c in contents)


def test_status_includes_created_at(client, test_archive):
    """Status endpoint includes created_at and client_ip from session metadata."""
    res = client.post(
        "/api/sessions/resume",
        json={"model": "test-model", "filename": test_archive},
    )
    sid = res.json()["session_id"]

    status = client.get(f"/api/sessions/{sid}/status")
    stats = status.json()
    assert "created_at" in stats
    assert stats["created_at"] != ""
    assert "client_ip" in stats
