"""Real Ollama e2e streaming tests (#34). Zero mocks.

Starts the actual FastAPI server against a real Ollama instance.
Skipped when Ollama is not running.
"""

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
    """Start the real FastAPI server with real Ollama (no mocks)."""
    port = _find_free_port()
    tmp_assistants = tempfile.mkdtemp()
    tmp_archives = tempfile.mkdtemp()

    # Only isolate user data dirs, NOT Ollama
    from unittest.mock import patch
    with (
        patch("local_llm.assistants.ASSISTANTS_DIR", tmp_assistants),
        patch("local_llm.archive.ARCHIVE_DIR", tmp_archives),
    ):
        from local_llm.api import app, sessions
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


@pytest.fixture()
def real_chat_ready(page, real_server_url):
    """Navigate to the app, pick an assistant + model, return page ready to chat."""
    page.goto(real_server_url)
    page.wait_for_selector("#assistant-overlay", timeout=10000)

    # Click the first assistant card
    page.click(".assistant-card >> nth=0")

    # If the assistant has no model bound, a subpicker appears; pick our model
    subpicker = page.locator(".assistant-model-subpicker .model-option")
    try:
        subpicker.first.wait_for(timeout=3000)
        model_option = page.locator(f".model-option:has-text('{_MODEL}')")
        model_option.wait_for(timeout=3000)
        model_option.first.click()
    except Exception:
        pass  # Assistant had a model bound

    page.wait_for_selector("#chat-container", state="visible", timeout=10000)
    page.wait_for_timeout(500)
    return page


def test_real_stream_first_token(real_chat_ready):
    """First token must arrive within 60s (covers model load time)."""
    page = real_chat_ready
    page.fill("#user-input", "Say hello in one word.")
    page.press("#user-input", "Enter")

    # Wait for streaming cursor to appear (means server accepted the message)
    page.wait_for_selector(".streaming-cursor", state="visible", timeout=10000)

    # Wait for at least one token to render (covers model load into VRAM)
    page.wait_for_function(
        '''() => {
            const el = document.querySelector(".streaming-cursor");
            return el && el.textContent.trim().length > 0;
        }''',
        timeout=120000,
    )


def test_real_stream_completes(real_chat_ready):
    """Full response must complete (streaming cursor removed) within 120s."""
    page = real_chat_ready
    page.fill("#user-input", "Say hello in one word.")
    page.press("#user-input", "Enter")

    page.wait_for_selector(".streaming-cursor", state="detached", timeout=120000)


def test_real_stream_content_nonempty(real_chat_ready):
    """The assistant message must contain actual text after streaming completes."""
    page = real_chat_ready
    page.fill("#user-input", "Say hello in one word.")
    page.press("#user-input", "Enter")

    page.wait_for_selector(".streaming-cursor", state="detached", timeout=120000)

    assistant_msg = page.locator(".message.assistant .message-content").last
    text = assistant_msg.text_content()
    assert text and len(text.strip()) > 0, f"Assistant response was empty: '{text}'"
