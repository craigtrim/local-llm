"""Tests for the context status modal."""


def test_click_context_bar_opens_modal(chat_ready):
    """Clicking the context bar opens the context modal."""
    page = chat_ready
    page.click("#context-bar")
    page.wait_for_selector("#context-overlay", state="visible")
    modal = page.locator(".context-modal")
    assert modal.is_visible()


def test_modal_shows_metrics(chat_ready):
    """The modal displays context metrics."""
    page = chat_ready
    page.click("#context-bar")
    page.wait_for_selector("#context-overlay", state="visible")
    body = page.locator("#context-modal-body").text_content()
    assert "%" in body
    assert "tokens" in body
    assert "exchanges" in body


def test_modal_close_button(chat_ready):
    """Clicking the X button closes the modal."""
    page = chat_ready
    page.click("#context-bar")
    page.wait_for_selector("#context-overlay", state="visible")
    page.click("#context-close-btn")
    page.wait_for_selector("#context-overlay", state="hidden")


def test_modal_backdrop_close(chat_ready):
    """Clicking the backdrop closes the modal."""
    page = chat_ready
    page.click("#context-bar")
    page.wait_for_selector("#context-overlay", state="visible")
    # Click the overlay itself (outside the modal)
    page.locator("#context-overlay").click(position={"x": 10, "y": 10})
    page.wait_for_selector("#context-overlay", state="hidden")


def test_modal_compact(chat_ready):
    """Clicking Compact triggers compaction and closes the modal (#55)."""
    page = chat_ready

    # Send a message first
    page.fill("#user-input", "hello")
    page.press("#user-input", "Enter")
    page.wait_for_selector(".streaming-cursor", state="detached", timeout=10000)
    msg_count = page.locator(".message").count()
    assert msg_count >= 2

    # Open modal and compact
    page.click("#context-bar")
    page.wait_for_selector("#context-overlay", state="visible")
    page.click("#context-compact-btn")

    # Modal should close and messages should still be present
    page.wait_for_selector("#context-overlay", state="hidden", timeout=10000)
    assert page.locator(".message").count() == msg_count


def test_modal_has_info_tooltip(chat_ready):
    """The [?] info trigger is present in the modal."""
    page = chat_ready
    page.click("#context-bar")
    page.wait_for_selector("#context-overlay", state="visible")
    trigger = page.locator(".context-info-trigger")
    assert trigger.is_visible()
    assert "?" in trigger.text_content()


def test_pct_display_capped_at_100(chat_ready):
    """The context bar percentage never exceeds 100%."""
    page = chat_ready
    # The percentage text should always be <= 100
    pct_text = page.locator(".context-pct").text_content()
    pct_val = int(pct_text.replace("%", ""))
    assert pct_val <= 100
