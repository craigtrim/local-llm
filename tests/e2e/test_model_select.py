from .conftest import FAKE_MODELS


def test_model_overlay_shown_on_load(chat_page):
    """Model selection overlay is visible on initial load."""
    overlay = chat_page.locator("#model-overlay")
    assert overlay.is_visible()

    chat = chat_page.locator("#chat-container")
    assert not chat.is_visible()


def test_model_buttons_rendered(chat_page):
    """All available models appear as buttons."""
    buttons = chat_page.locator(".model-option")
    assert buttons.count() == len(FAKE_MODELS)

    for i, model_name in enumerate(FAKE_MODELS):
        assert buttons.nth(i).text_content() == model_name


def test_select_model_opens_chat(chat_page):
    """Clicking a model hides the overlay and shows the chat view."""
    chat_page.click(".model-option >> nth=0")
    chat_page.wait_for_selector("#chat-container", state="visible")

    overlay = chat_page.locator("#model-overlay")
    assert not overlay.is_visible()

    header_model = chat_page.locator("#header-model")
    assert header_model.text_content() == FAKE_MODELS[0]


def test_input_focused_after_model_select(chat_page):
    """Input textarea is focused after selecting a model."""
    chat_page.click(".model-option >> nth=0")
    chat_page.wait_for_selector("#chat-container", state="visible")
    chat_page.wait_for_timeout(200)

    focused = chat_page.evaluate("document.activeElement.id")
    assert focused == "user-input"
