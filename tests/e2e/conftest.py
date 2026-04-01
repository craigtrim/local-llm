import socket
import threading
import time
from unittest.mock import patch

import pytest
import uvicorn

FAKE_MODELS = ["test-model-13b", "test-model-7b"]  # sorted order (client.list_models sorts)
FAKE_RESPONSE = "Hello! I am a test assistant ready to help you."


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

    with (
        patch("ollama.chat", side_effect=_fake_ollama_chat),
        patch("ollama.list", side_effect=_fake_ollama_list),
        patch("ollama.show", side_effect=_fake_ollama_show),
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

        # Wait for server to be ready
        for _ in range(50):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                    break
            except OSError:
                time.sleep(0.1)

        yield f"http://127.0.0.1:{port}"

        server.should_exit = True
        thread.join(timeout=3)


@pytest.fixture()
def chat_page(page, server_url):
    """Navigate to the app and return the page."""
    page.goto(server_url)
    page.wait_for_selector("#model-overlay")
    return page


@pytest.fixture()
def chat_ready(chat_page):
    """Select the first model and return a page ready for chatting."""
    chat_page.click(".model-option >> nth=0")
    chat_page.wait_for_selector("#chat-container", state="visible")
    # Wait for WebSocket to connect
    chat_page.wait_for_timeout(500)
    return chat_page
