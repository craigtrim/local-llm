"""Real Ollama greeting tests (#40). Zero mocks on Ollama.

Uses the shared real_server_url fixture from conftest.py.
Skipped when Ollama is not running.
"""

import json
import urllib.request

import pytest

from .conftest import REAL_MODEL, _REAL_OLLAMA_AVAILABLE

pytestmark = pytest.mark.skipif(
    not _REAL_OLLAMA_AVAILABLE,
    reason=f"Ollama not running or {REAL_MODEL} not available",
)


def test_real_greeting_generation(real_server_url):
    """Create an assistant with real Ollama, verify greetings generated."""
    data = json.dumps({
        "name": "Greeter", "model": REAL_MODEL,
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
    data = json.dumps({
        "name": "UIGreeter", "model": REAL_MODEL,
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

    page.goto(real_server_url)
    page.wait_for_selector("#assistant-overlay", timeout=60000)

    card = page.locator(".assistant-card:has-text('UIGreeter')")
    card.wait_for(timeout=60000)
    card.click()

    subpicker = page.locator(".assistant-model-subpicker .model-option")
    try:
        subpicker.first.wait_for(timeout=60000)
        model_option = page.locator(f".model-option:has-text('{REAL_MODEL}')")
        model_option.wait_for(timeout=60000)
        model_option.first.click()
    except Exception:
        pass

    page.wait_for_selector("#chat-container", state="visible", timeout=60000)
    greeting = page.locator(".message.greeting .message-content").first
    greeting.wait_for(timeout=60000)
    text = greeting.text_content()
    assert text and len(text.strip()) > 0, f"Greeting was empty: {text!r}"
