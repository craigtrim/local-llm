import socket
import tempfile
import threading
import time
from unittest.mock import patch

import pytest
import uvicorn

FAKE_MODELS = ["test-model-13b", "test-model-7b"]  # sorted order (client.list_models sorts)
FAKE_RESPONSE = "Hello! I am a test assistant ready to help you."
FAKE_GREETINGS = [f"Greeting {i}!" for i in range(20)]


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _FakeModelInfo:
    def __init__(self, name: str):
        self.model = name


class _FakeListResponse:
    def __init__(self):
        self.models = [_FakeModelInfo(m) for m in FAKE_MODELS]


def _fake_ollama_chat(model, messages, stream=False):
    import json as _json
    _OLLAMA_KEYS = {"role", "content", "images"}
    for msg in messages:
        unexpected = set(msg.keys()) - _OLLAMA_KEYS
        assert not unexpected, f"Unexpected keys sent to Ollama: {unexpected}"
    # Detect greeting generation prompt
    user_text = messages[-1].get("content", "") if messages else ""
    if "unique greeting messages" in user_text and "JSON array" in user_text:
        return {"message": {"content": _json.dumps(FAKE_GREETINGS)}}
    if stream:
        def _stream():
            for word in FAKE_RESPONSE.split():
                yield {"message": {"content": word + " "}}
        return _stream()
    return {"message": {"content": FAKE_RESPONSE}}


def _fake_ollama_list():
    return _FakeListResponse()


def _fake_ollama_show(model):
    return {"model_info": {"llama.context_length": 4096}}


@pytest.fixture(scope="session")
def server_url():
    """Start the real FastAPI server with mocked ollama on a random port."""
    port = _find_free_port()

    import json as _json

    # Isolate e2e tests from real user data (see #17)
    tmp_assistants = tempfile.mkdtemp()
    tmp_archives = tempfile.mkdtemp()

    # Pre-populate default assistant with greetings so greeting tests work
    default_assistant = {
        "id": "default", "uuid": "00000000000000000000000000000000",
        "name": "Default", "description": "General-purpose assistant",
        "avatar_color": "#6b9fdb", "model": None,
        "system_prompt": "You are a helpful assistant.",
        "context_tokens": None, "token_estimate_ratio": None,
        "context_reserve": None, "version": 1,
        "greetings": FAKE_GREETINGS,
    }
    with open(f"{tmp_assistants}/default.json", "w") as f:
        _json.dump(default_assistant, f)

    with (
        patch("ollama.chat", side_effect=_fake_ollama_chat),
        patch("ollama.list", side_effect=_fake_ollama_list),
        patch("ollama.show", side_effect=_fake_ollama_show),
        patch("local_llm.assistants.ASSISTANTS_DIR", tmp_assistants),
        patch("local_llm.archive.ARCHIVE_DIR", tmp_archives),
    ):
        # Import app AFTER patching so module-level state picks up mocks
        from local_llm.api import app, sessions

        # Clear any leftover sessions between runs
        sessions.clear()

        server = uvicorn.Server(
            uvicorn.Config(
                app=app,
                host="127.0.0.1",
                port=port,
                log_level="warning",
            )
        )
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()

        # Wait for server to be fully ready (not just accepting TCP)
        import urllib.request
        for _ in range(50):
            try:
                urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/api/models", timeout=0.5
                )
                break
            except Exception:
                time.sleep(0.1)

        yield f"http://127.0.0.1:{port}"

        server.should_exit = True
        thread.join(timeout=3)


@pytest.fixture(scope="session")
def test_archive(server_url):
    """Create a test archive file for resume tests."""
    from local_llm.archive import save

    messages = [
        {"role": "system", "content": "You are a helpful assistant.", "timestamp": "2026-04-01T12:00:00+00:00"},
        {"role": "user", "content": "Remember the code word is banana.", "timestamp": "2026-04-01T12:00:05+00:00"},
        {"role": "assistant", "content": "Got it, the code word is banana.", "timestamp": "2026-04-01T12:00:07+00:00"},
    ]
    path = save(messages, title="Code word test", model="test-model-7b", client_ip="127.0.0.1", user_agent="TestAgent")
    yield path.name
    path.unlink(missing_ok=True)


@pytest.fixture()
def chat_page(page, server_url):
    """Navigate to the app and return the page."""
    page.goto(server_url)
    page.wait_for_selector("#assistant-overlay")
    return page


@pytest.fixture()
def chat_ready(chat_page):
    """Select the first assistant and return a page ready for chatting."""
    chat_page.click(".assistant-card >> nth=0")
    # If the assistant has no model bound, a subpicker appears; click first model
    subpicker = chat_page.locator(".assistant-model-subpicker .model-option")
    try:
        subpicker.first.wait_for(timeout=2000)
        subpicker.first.click()
    except Exception:
        pass  # Assistant had a model bound, went straight to chat
    chat_page.wait_for_selector("#chat-container", state="visible")
    # Wait for WebSocket to connect
    chat_page.wait_for_timeout(500)
    return chat_page


# --- Real Ollama fixtures (no mocks) ---

REAL_MODEL = "qwen2.5:7b"

try:
    import ollama as _ollama_check
    _ollama_check.show(REAL_MODEL)
    _REAL_OLLAMA_AVAILABLE = True
except Exception:
    _REAL_OLLAMA_AVAILABLE = False


@pytest.fixture(scope="session")
def real_server_url():
    """Start the real FastAPI server with real Ollama (no mocks).

    Session-scoped so all real-Ollama test files share one server.
    Skipped when Ollama is not running.
    """
    if not _REAL_OLLAMA_AVAILABLE:
        pytest.skip(f"Ollama not running or {REAL_MODEL} not available")

    port = _find_free_port()
    _tmp_assistants = tempfile.mkdtemp()
    _tmp_archives = tempfile.mkdtemp()

    with (
        patch("local_llm.assistants.ASSISTANTS_DIR", _tmp_assistants),
        patch("local_llm.archive.ARCHIVE_DIR", _tmp_archives),
    ):
        from local_llm.api import app as _app
        from local_llm.api import sessions as _sessions
        _sessions.clear()

        _server = uvicorn.Server(
            uvicorn.Config(
                app=_app,
                host="127.0.0.1",
                port=port,
                log_level="warning",
            )
        )
        _thread = threading.Thread(target=_server.run, daemon=True)
        _thread.start()

        import urllib.request
        for _ in range(50):
            try:
                urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/api/models", timeout=0.5
                )
                break
            except Exception:
                time.sleep(0.1)

        yield f"http://127.0.0.1:{port}"

        _server.should_exit = True
        _thread.join(timeout=3)
