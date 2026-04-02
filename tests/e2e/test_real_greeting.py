"""Real Ollama greeting tests (#40). Zero mocks on Ollama.

Skipped when Ollama is not running.
"""

import json
import socket
import tempfile
import threading
import time

import pytest
import uvicorn

_MODEL = "qwen2.5:7b"

try:
    import ollama as ollama_lib
    ollama_lib.show(_MODEL)
    _OLLAMA_AVAILABLE = True
except Exception:
    _OLLAMA_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _OLLAMA_AVAILABLE,
    reason=f"Ollama not running or {_MODEL} not available",
)


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def real_server_url():
    port = _find_free_port()
    tmp_assistants = tempfile.mkdtemp()
    tmp_archives = tempfile.mkdtemp()

    from unittest.mock import patch
    with (
        patch("local_llm.assistants.ASSISTANTS_DIR", tmp_assistants),
        patch("local_llm.archive.ARCHIVE_DIR", tmp_archives),
    ):
        from local_llm.api import app, sessions
        sessions.clear()

        server = uvicorn.Server(
            uvicorn.Config(app=app, host="127.0.0.1", port=port, log_level="warning")
        )
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()

        import urllib.request
        for _ in range(50):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/models", timeout=0.5)
                break
            except Exception:
                time.sleep(0.1)

        yield f"http://127.0.0.1:{port}"
        server.should_exit = True
        thread.join(timeout=3)


def test_real_greeting_generation(real_server_url):
    """Create an assistant with real Ollama, verify greetings generated."""
    import urllib.request
    data = json.dumps({
        "name": "Greeter", "model": _MODEL,
        "system_prompt": "You are a friendly greeter who welcomes people warmly."
    }).encode()
    req = urllib.request.Request(
        f"{real_server_url}/api/assistants",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    resp = urllib.request.urlopen(req, timeout=120)
    result = json.loads(resp.read())
    assert "greetings" in result
    assert len(result["greetings"]) > 0, "No greetings generated"
    assert all(isinstance(g, str) and g.strip() for g in result["greetings"])


def test_real_greeting_displayed(real_server_url, page):
    """Full pipeline: create assistant with real Ollama, verify greeting in UI."""
    import urllib.request
    # Create an assistant that has greetings
    data = json.dumps({
        "name": "UIGreeter", "model": _MODEL,
        "system_prompt": "You are a friendly assistant."
    }).encode()
    req = urllib.request.Request(
        f"{real_server_url}/api/assistants",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    resp = urllib.request.urlopen(req, timeout=120)
    assistant = json.loads(resp.read())
    assert len(assistant.get("greetings", [])) > 0, "Assistant has no greetings"

    # Now start a session via the UI
    page.goto(real_server_url)
    page.wait_for_selector("#assistant-overlay", timeout=10000)

    # Click the assistant we just created
    card = page.locator(f".assistant-card:has-text('UIGreeter')")
    card.wait_for(timeout=5000)
    card.click()

    subpicker = page.locator(".assistant-model-subpicker .model-option")
    try:
        subpicker.first.wait_for(timeout=3000)
        model_option = page.locator(f".model-option:has-text('{_MODEL}')")
        model_option.wait_for(timeout=3000)
        model_option.first.click()
    except Exception:
        pass

    page.wait_for_selector("#chat-container", state="visible", timeout=10000)
    # Greeting should appear as first assistant message
    greeting = page.locator(".message.greeting .message-content").first
    greeting.wait_for(timeout=5000)
    text = greeting.text_content()
    assert text and len(text.strip()) > 0, f"Greeting was empty: {text!r}"
