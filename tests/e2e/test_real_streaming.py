"""Real Ollama e2e streaming tests (#34). Zero mocks.

Uses the shared real_server_url fixture from conftest.py.
Skipped when Ollama is not running.
"""

import pytest

from .conftest import REAL_MODEL, _REAL_OLLAMA_AVAILABLE

pytestmark = pytest.mark.skipif(
    not _REAL_OLLAMA_AVAILABLE,
    reason=f"Ollama not running or {REAL_MODEL} not available",
)


@pytest.fixture()
def real_chat_ready(page, real_server_url):
    """Navigate to the app, pick an assistant + model, return page ready to chat."""
    page.goto(real_server_url)
    page.wait_for_selector("#assistant-overlay", timeout=60000)

    page.click(".assistant-card >> nth=0")

    subpicker = page.locator(".assistant-model-subpicker .model-option")
    try:
        subpicker.first.wait_for(timeout=60000)
        model_option = page.locator(f".model-option:has-text('{REAL_MODEL}')")
        model_option.wait_for(timeout=60000)
        model_option.first.click()
    except Exception:
        pass

    page.wait_for_selector("#chat-container", state="visible", timeout=60000)
    page.wait_for_timeout(500)
    return page


def test_real_stream_first_token(real_chat_ready):
    """First token must arrive within 120s (covers model load time)."""
    page = real_chat_ready
    page.fill("#user-input", "Say hello in one word.")
    page.press("#user-input", "Enter")

    page.wait_for_selector(".streaming-cursor", state="visible", timeout=60000)

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

    assistant_msg = page.locator(".message.assistant:not(.greeting) .message-content").last
    text = assistant_msg.text_content()
    assert text and len(text.strip()) > 0, f"Assistant response was empty: '{text}'"
