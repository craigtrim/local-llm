"""Tests for wizard step dot click navigation (#42)."""


def _open_wizard(page):
    """Open the assistant creation wizard."""
    page.click("#create-assistant-btn")
    page.wait_for_selector(".assistant-wizard", state="visible")


def _fill_step1(page):
    page.fill("#wizard-name", "Test Bot")


def _fill_step2(page):
    page.locator("#wizard-model-list .model-option").first.wait_for(timeout=3000)
    page.locator("#wizard-model-list .model-option").first.click()


def _fill_step3(page):
    page.fill("#wizard-system-prompt", "You are helpful.")


def _current_step(page):
    return int(page.locator(".wizard-step-dot.active").get_attribute("data-step"))


def test_click_step_dot_backward(chat_page):
    """Clicking a previous step dot navigates backward."""
    _open_wizard(chat_page)
    _fill_step1(chat_page)
    chat_page.click("#wizard-next")
    assert _current_step(chat_page) == 2

    chat_page.click(".wizard-step-dot[data-step='1']")
    assert _current_step(chat_page) == 1


def test_click_step_dot_forward_with_validation(chat_page):
    """Clicking a future step dot validates intermediate steps."""
    _open_wizard(chat_page)

    # Step 1 is empty, clicking step 3 should fail validation and stay on 1
    chat_page.click(".wizard-step-dot[data-step='3']")
    assert _current_step(chat_page) == 1


def test_click_step_dot_forward_when_valid(chat_page):
    """Clicking a future step dot works when intermediate steps are valid."""
    _open_wizard(chat_page)
    _fill_step1(chat_page)
    chat_page.click("#wizard-next")
    _fill_step2(chat_page)

    # Now on step 2 with valid data, click step dot 1 then jump to 3
    chat_page.click(".wizard-step-dot[data-step='1']")
    assert _current_step(chat_page) == 1

    # Jump from 1 to 3 (validates 1 and 2, both filled)
    chat_page.click(".wizard-step-dot[data-step='3']")
    assert _current_step(chat_page) == 3


def test_click_step_dot_jump_to_4(chat_page):
    """Can jump from step 1 to step 4 when all intermediate steps are valid."""
    _open_wizard(chat_page)
    _fill_step1(chat_page)
    chat_page.click("#wizard-next")
    _fill_step2(chat_page)
    chat_page.click("#wizard-next")
    _fill_step3(chat_page)

    # Go back to step 1
    chat_page.click(".wizard-step-dot[data-step='1']")
    assert _current_step(chat_page) == 1

    # Jump directly to step 4
    chat_page.click(".wizard-step-dot[data-step='4']")
    assert _current_step(chat_page) == 4
