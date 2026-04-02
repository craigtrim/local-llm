"""API-level tests verifying no duplicate archives on resume/switch (#47).

Hits the real server endpoints and WebSocket to trigger auto-save,
then checks /api/archives for file counts. No Playwright/DOM involved.
"""

import json

import pytest
import websockets.sync.client as ws_client


def _create_session_and_chat(base_url, model="test-model-7b"):
    """Create a session, send a message via WebSocket, return (session_id, archive_count)."""
    import urllib.request

    # Create session
    data = json.dumps({"model": model}).encode()
    req = urllib.request.Request(
        f"{base_url}/api/sessions",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    resp = urllib.request.urlopen(req, timeout=10)
    session = json.loads(resp.read())
    sid = session["session_id"]

    # Send a message via WebSocket to trigger auto-save
    ws_url = base_url.replace("http://", "ws://") + f"/ws/chat/{sid}"
    with ws_client.connect(ws_url) as ws:
        ws.send("test message for archive")
        # Read until we get a "done" message
        while True:
            msg = json.loads(ws.recv())
            if msg["type"] in ("done", "stopped", "error"):
                break

    return sid


def _get_archive_count(base_url):
    import urllib.request
    resp = urllib.request.urlopen(f"{base_url}/api/archives", timeout=10)
    data = json.loads(resp.read())
    return len(data.get("archives", []))


def _get_archives(base_url):
    import urllib.request
    resp = urllib.request.urlopen(f"{base_url}/api/archives", timeout=10)
    data = json.loads(resp.read())
    return data.get("archives", [])


def _resume_session(base_url, filename, model="test-model-7b"):
    import urllib.request
    data = json.dumps({"filename": filename, "model": model}).encode()
    req = urllib.request.Request(
        f"{base_url}/api/sessions/resume",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    resp = urllib.request.urlopen(req, timeout=10)
    return json.loads(resp.read())


def _clear_session(base_url, sid):
    import urllib.request
    req = urllib.request.Request(
        f"{base_url}/api/sessions/{sid}/clear",
        method="POST",
    )
    resp = urllib.request.urlopen(req, timeout=10)
    return json.loads(resp.read())


def test_resume_and_switch_no_new_file(server_url):
    """Resume archive A, then clear (switch away). No new archive should be created."""
    # Create a session and chat to produce archive A
    _create_session_and_chat(server_url)

    archives = _get_archives(server_url)
    count_before = len(archives)
    assert count_before >= 1

    filename = archives[0]["filename"]

    # Resume archive A
    resumed = _resume_session(server_url, filename)
    resumed_sid = resumed["session_id"]

    # Switch away (clear) without sending any new messages
    _clear_session(server_url, resumed_sid)

    # Archive count should not increase
    count_after = _get_archive_count(server_url)
    assert count_after == count_before, (
        f"Archive count changed from {count_before} to {count_after} after resume+clear with no new messages"
    )


def test_resume_chat_and_switch_overwrites(server_url):
    """Resume archive A, send a message, clear. A should be updated, not duplicated."""
    _create_session_and_chat(server_url)

    archives = _get_archives(server_url)
    count_before = len(archives)
    filename = archives[0]["filename"]

    # Resume and send a new message
    resumed = _resume_session(server_url, filename)
    resumed_sid = resumed["session_id"]

    ws_url = server_url.replace("http://", "ws://") + f"/ws/chat/{resumed_sid}"
    with ws_client.connect(ws_url) as ws:
        ws.send("follow up question after resume")
        while True:
            msg = json.loads(ws.recv())
            if msg["type"] in ("done", "stopped", "error"):
                break

    # Archive count should be the same (overwritten, not duplicated)
    count_after = _get_archive_count(server_url)
    assert count_after == count_before, (
        f"Archive count changed from {count_before} to {count_after} after resume+chat"
    )

    # The archive should contain the new message
    import urllib.request
    resp = urllib.request.urlopen(f"{server_url}/api/archives/{filename}", timeout=10)
    data = json.loads(resp.read())
    messages = data.get("messages", [])
    user_msgs = [m["content"] for m in messages if m["role"] == "user"]
    assert "follow up question after resume" in user_msgs


def test_fresh_session_chat_creates_one_archive(server_url):
    """A fresh session with 3 exchanges should produce exactly 1 archive, not 3."""
    count_before = _get_archive_count(server_url)

    # Create session
    import urllib.request
    data = json.dumps({"model": "test-model-7b"}).encode()
    req = urllib.request.Request(
        f"{server_url}/api/sessions",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    resp = urllib.request.urlopen(req, timeout=10)
    session = json.loads(resp.read())
    sid = session["session_id"]

    # Send 3 messages (each triggers auto-save)
    ws_url = server_url.replace("http://", "ws://") + f"/ws/chat/{sid}"
    with ws_client.connect(ws_url) as ws:
        for i in range(3):
            ws.send(f"question number {i}")
            while True:
                msg = json.loads(ws.recv())
                if msg["type"] in ("done", "stopped", "error"):
                    break

    # Should have exactly 1 new archive (not 3)
    count_after = _get_archive_count(server_url)
    assert count_after == count_before + 1, (
        f"Expected {count_before + 1} archives, got {count_after}"
    )
