from .conftest import FAKE_MODELS


def test_assistant_overlay_shown_on_load(chat_page):
    """Assistant selection overlay is visible on initial load."""
    overlay = chat_page.locator("#assistant-overlay")
    assert overlay.is_visible()

    chat = chat_page.locator("#chat-container")
    assert not chat.is_visible()


def test_assistant_cards_rendered(chat_page):
    """Default assistant card appears in the picker."""
    cards = chat_page.locator(".assistant-card")
    assert cards.count() >= 1  # at least the default assistant

    # The default assistant card should be present
    assert "Default" in cards.nth(0).text_content()


def test_select_assistant_opens_chat(chat_page):
    """Clicking an assistant (with model sub-pick) hides overlay and shows chat."""
    chat_page.click(".assistant-card >> nth=0")
    # Default assistant needs model sub-picker
    chat_page.wait_for_selector(".assistant-model-subpicker .model-option", timeout=5000)
    chat_page.click(".assistant-model-subpicker .model-option >> nth=0")
    chat_page.wait_for_selector("#chat-container", state="visible")

    overlay = chat_page.locator("#assistant-overlay")
    assert not overlay.is_visible()

    header_model = chat_page.locator("#header-model")
    assert header_model.text_content() == FAKE_MODELS[0]


def test_input_focused_after_assistant_select(chat_page):
    """Input textarea is focused after selecting an assistant."""
    chat_page.click(".assistant-card >> nth=0")
    chat_page.wait_for_selector(".assistant-model-subpicker .model-option", timeout=5000)
    chat_page.click(".assistant-model-subpicker .model-option >> nth=0")
    chat_page.wait_for_selector("#chat-container", state="visible")
    chat_page.wait_for_timeout(200)

    focused = chat_page.evaluate("document.activeElement.id")
    assert focused == "user-input"
