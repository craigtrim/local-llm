"""Test 3-dismiss pattern on all modals: close button, Escape, backdrop click (see #22)."""


# --- Context modal (#25) ---


def test_context_modal_close_button(chat_ready):
    """Context modal closes via the X button."""
    page = chat_ready
    page.click("#context-bar")
    page.wait_for_selector("#context-overlay", state="visible")

    page.click("#context-close-btn")
    page.wait_for_selector("#context-overlay", state="hidden", timeout=2000)


def test_context_modal_escape(chat_ready):
    """Context modal closes via Escape key."""
    page = chat_ready
    page.click("#context-bar")
    page.wait_for_selector("#context-overlay", state="visible")

    page.keyboard.press("Escape")
    page.wait_for_selector("#context-overlay", state="hidden", timeout=2000)


def test_context_modal_backdrop(chat_ready):
    """Context modal closes via backdrop click."""
    page = chat_ready
    page.click("#context-bar")
    page.wait_for_selector("#context-overlay", state="visible")

    # Click the overlay itself (not the modal content)
    page.locator("#context-overlay").click(position={"x": 10, "y": 10})
    page.wait_for_selector("#context-overlay", state="hidden", timeout=2000)


# --- Assistant wizard (#24) ---


def test_wizard_close_button(chat_ready):
    """Wizard closes via the X button."""
    page = chat_ready
    page.click("#sidebar-switch-assistant")
    page.wait_for_selector("#assistant-overlay", state="visible")

    page.click("#create-assistant-btn")
    page.wait_for_selector("#assistant-wizard-overlay", state="visible")

    page.click("#wizard-close-btn")
    page.wait_for_selector("#assistant-wizard-overlay", state="hidden", timeout=2000)


def test_wizard_escape(chat_ready):
    """Wizard closes via Escape key."""
    page = chat_ready
    page.click("#sidebar-switch-assistant")
    page.wait_for_selector("#assistant-overlay", state="visible")

    page.click("#create-assistant-btn")
    page.wait_for_selector("#assistant-wizard-overlay", state="visible")

    page.keyboard.press("Escape")
    page.wait_for_selector("#assistant-wizard-overlay", state="hidden", timeout=2000)


def test_wizard_backdrop(chat_ready):
    """Wizard closes via backdrop click."""
    page = chat_ready
    page.click("#sidebar-switch-assistant")
    page.wait_for_selector("#assistant-overlay", state="visible")

    page.click("#create-assistant-btn")
    page.wait_for_selector("#assistant-wizard-overlay", state="visible")

    page.locator("#assistant-wizard-overlay").click(position={"x": 10, "y": 10})
    page.wait_for_selector("#assistant-wizard-overlay", state="hidden", timeout=2000)


# --- Assistant picker (#23) ---


def test_picker_close_button(chat_ready):
    """Assistant picker closes via the X button when a session exists."""
    page = chat_ready
    page.click("#sidebar-switch-assistant")
    page.wait_for_selector("#assistant-overlay", state="visible")

    page.click("#assistant-picker-close")
    page.wait_for_selector("#assistant-overlay", state="hidden", timeout=2000)
    page.wait_for_selector("#chat-container", state="visible")


def test_picker_escape(chat_ready):
    """Assistant picker closes via Escape when a session exists."""
    page = chat_ready
    page.click("#sidebar-switch-assistant")
    page.wait_for_selector("#assistant-overlay", state="visible")

    page.keyboard.press("Escape")
    page.wait_for_selector("#assistant-overlay", state="hidden", timeout=2000)
    page.wait_for_selector("#chat-container", state="visible")


def test_picker_backdrop(chat_ready):
    """Assistant picker closes via backdrop click when a session exists."""
    page = chat_ready
    page.click("#sidebar-switch-assistant")
    page.wait_for_selector("#assistant-overlay", state="visible")

    page.locator("#assistant-overlay").click(position={"x": 10, "y": 10})
    page.wait_for_selector("#assistant-overlay", state="hidden", timeout=2000)
    page.wait_for_selector("#chat-container", state="visible")
