"""E2E tests for system prompt wrapping (#57).

Hits the real FastAPI server (mocked ollama) via HTTP/WebSocket.
No Playwright/DOM involved.
"""

import json
import urllib.request

import websockets.sync.client as ws_client

import tests.e2e.conftest as _conftest


def _mock():
    """Get the mock ollama.chat, which is only set after server_url starts."""
    return _conftest.mock_ollama_chat


def _post_json(url, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    resp = urllib.request.urlopen(req, timeout=10)
    return json.loads(resp.read())


def _create_assistant(base_url, name, system_prompt, wrap=None):
    """Create an assistant and return its config."""
    payload = {
        "name": name,
        "model": "test-model-7b",
        "system_prompt": system_prompt,
    }
    if wrap is not None:
        payload["wrap_system_prompt"] = wrap
    return _post_json(f"{base_url}/api/assistants", payload)


def _create_session_with_assistant(base_url, assistant_id):
    """Create a session for the given assistant."""
    return _post_json(f"{base_url}/api/sessions", {
        "model": "test-model-7b",
        "assistant_id": assistant_id,
    })


def _send_message(base_url, session_id, text):
    """Send a message via WebSocket and wait for completion."""
    ws_url = base_url.replace("http://", "ws://") + f"/ws/chat/{session_id}"
    with ws_client.connect(ws_url) as ws:
        ws.send(text)
        while True:
            msg = json.loads(ws.recv())
            if msg["type"] in ("done", "stopped", "error"):
                break


def _get_system_messages_from_mock():
    """Extract system messages from all ollama.chat calls."""
    system_msgs = []
    for call in _mock().call_args_list:
        messages = call.kwargs.get("messages") or call.args[1] if len(call.args) > 1 else []
        if not messages and "messages" in (call.kwargs or {}):
            messages = call.kwargs["messages"]
        for m in messages:
            if m.get("role") == "system":
                system_msgs.append(m["content"])
    return system_msgs


def test_wrapped_prompt_reaches_ollama(server_url):
    """System prompt wrapper is applied and reaches ollama.chat (#57)."""
    assistant = _create_assistant(
        server_url, "Wrapper Test Bot", "You help with testing."
    )
    session = _create_session_with_assistant(server_url, assistant["id"])

    _mock().reset_mock()
    _send_message(server_url, session["session_id"], "hello")

    system_msgs = _get_system_messages_from_mock()
    assert len(system_msgs) >= 1, "Expected at least one system message in ollama.chat calls"
    # The system message should contain both the raw prompt and the wrapper guidelines
    assert "You help with testing." in system_msgs[0]
    assert "Behavioral Guidelines" in system_msgs[0]


def test_opt_out_skips_wrapper(server_url):
    """Assistant with wrap_system_prompt=false skips wrapping (#57)."""
    assistant = _create_assistant(
        server_url, "Unwrapped Bot", "You help with testing.", wrap=False,
    )
    session = _create_session_with_assistant(server_url, assistant["id"])

    _mock().reset_mock()
    _send_message(server_url, session["session_id"], "hello")

    system_msgs = _get_system_messages_from_mock()
    assert len(system_msgs) >= 1
    assert "You help with testing." in system_msgs[0]
    assert "Behavioral Guidelines" not in system_msgs[0]


def test_greeting_uses_raw_prompt(server_url):
    """Greeting generation should use the raw prompt, not the wrapped one (#57)."""
    # The greeting generation happens at assistant save time via generate_greetings_fn.
    # The fake ollama.chat in conftest detects greeting prompts by content.
    # We just need to verify that the greetings were generated and don't contain
    # wrapper text.
    assistant = _create_assistant(
        server_url, "Greeting Wrapper Test", "You are a pirate captain."
    )
    greetings = assistant.get("greetings", [])
    # Greetings should exist (conftest fake returns them for greeting prompts)
    assert len(greetings) > 0
    # None of the greetings should contain wrapper boilerplate
    for g in greetings:
        assert "Behavioral Guidelines" not in g
