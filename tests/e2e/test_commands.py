from .conftest import FAKE_MODELS


def test_clear_resets_conversation(chat_ready):
    """The /clear command archives and resets the chat."""
    page = chat_ready

    # Send a message
    page.fill("#user-input", "hello")
    page.press("#user-input", "Enter")
    page.wait_for_selector(".streaming-cursor", state="detached", timeout=10000)

    # Verify messages exist
    assert page.locator(".message.user").count() == 1
    assert page.locator(".message.assistant").count() == 1

    # Execute /clear
    page.fill("#user-input", "/clear")
    page.press("#user-input", "Enter")

    # Wait for the system message
    page.wait_for_selector(".message.system", timeout=5000)

    # Old messages should be gone, only system message remains
    assert page.locator(".message.user").count() == 0
    assert page.locator(".message.assistant").count() == 0
    assert "Conversation cleared" in page.locator(".message.system").text_content()


def test_model_switch_shows_overlay(chat_ready):
    """The /model header button shows the model selection overlay."""
    page = chat_ready

    page.click("#model-btn")

    page.wait_for_selector("#model-overlay", state="visible", timeout=3000)
    assert not page.locator("#chat-container").is_visible()

    # Model buttons should still be rendered
    buttons = page.locator(".model-option")
    assert buttons.count() == len(FAKE_MODELS)


def test_status_shows_details(chat_ready):
    """Clicking the context bar shows full status details in chat."""
    page = chat_ready

    # Send a message so stats are non-trivial
    page.fill("#user-input", "hello")
    page.press("#user-input", "Enter")
    page.wait_for_selector(".streaming-cursor", state="detached", timeout=10000)

    # Click context bar
    page.click("#context-bar")

    # Status grid should appear
    page.wait_for_selector(".status-grid", timeout=5000)
    grid = page.locator(".status-grid")
    text = grid.text_content()
    assert "Q&A" in text
    assert "Summaries" in text
    assert "Model" in text


def test_clear_via_header_button(chat_ready):
    """The /clear header button works the same as typing /clear."""
    page = chat_ready

    page.fill("#user-input", "hello")
    page.press("#user-input", "Enter")
    page.wait_for_selector(".streaming-cursor", state="detached", timeout=10000)

    page.click("#clear-btn")

    page.wait_for_selector(".message.system", timeout=5000)
    assert page.locator(".message.user").count() == 0
    assert "Conversation cleared" in page.locator(".message.system").text_content()
