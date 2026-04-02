"""Tests for wizard advanced settings sliders (#43)."""


def _open_wizard_step4(page):
    """Navigate to wizard step 4 with valid data in steps 1-3."""
    page.click("#create-assistant-btn")
    page.wait_for_selector(".assistant-wizard", state="visible")
    page.fill("#wizard-name", "Slider Test Bot")
    page.click("#wizard-next")
    page.locator("#wizard-model-list .model-option").first.wait_for(timeout=3000)
    page.locator("#wizard-model-list .model-option").first.click()
    page.click("#wizard-next")
    page.fill("#wizard-system-prompt", "You are helpful.")
    page.click("#wizard-next")
    # Expand advanced settings
    page.click("#wizard-advanced-toggle")
    page.wait_for_selector("#wizard-advanced-content", state="visible")


def test_sliders_render_on_step_4(chat_page):
    """All 3 sliders exist on step 4."""
    _open_wizard_step4(chat_page)
    assert chat_page.locator("#wizard-context-tokens").get_attribute("type") == "range"
    assert chat_page.locator("#wizard-token-ratio").get_attribute("type") == "range"
    assert chat_page.locator("#wizard-context-reserve").get_attribute("type") == "range"


def test_sliders_show_default_values(chat_page):
    """Each slider's value label shows the default."""
    _open_wizard_step4(chat_page)
    assert chat_page.locator("#wizard-context-tokens-val").text_content() == "4096"
    assert chat_page.locator("#wizard-token-ratio-val").text_content() == "4"
    assert chat_page.locator("#wizard-context-reserve-val").text_content() == "512"


def test_slider_updates_value_label(chat_page):
    """Moving a slider updates the displayed value."""
    _open_wizard_step4(chat_page)
    slider = chat_page.locator("#wizard-context-tokens")
    slider.fill("8192")
    label = chat_page.locator("#wizard-context-tokens-val").text_content()
    assert label == "8192"


def test_slider_value_submitted(chat_page):
    """Custom slider values are saved to the assistant."""
    _open_wizard_step4(chat_page)
    chat_page.locator("#wizard-context-tokens").fill("16384")
    chat_page.locator("#wizard-context-reserve").fill("1024")
    chat_page.click("#wizard-save")
    chat_page.wait_for_selector(".assistant-wizard", state="hidden")

    # Verify via API
    response = chat_page.evaluate("() => fetch('/api/assistants').then(r => r.json())")
    bot = next(a for a in response["assistants"] if a["name"] == "Slider Test Bot")
    assert bot["context_tokens"] == 16384
    assert bot["context_reserve"] == 1024
