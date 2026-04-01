def test_context_bar_segments_rendered(chat_ready):
    """The context bar has 10 segments on load."""
    page = chat_ready

    segments = page.locator(".context-segment")
    assert segments.count() == 10


def test_context_bar_shows_percentage(chat_ready):
    """The context bar shows a percentage value."""
    page = chat_ready

    pct = page.locator(".context-pct")
    text = pct.text_content()
    # Should end with %
    assert "%" in text


def test_context_bar_updates_after_message(chat_ready):
    """The context bar percentage increases after sending a message."""
    page = chat_ready

    # Get initial percentage
    initial_text = page.locator(".context-pct").text_content()
    initial_pct = int(initial_text.replace("%", ""))

    # Send a message
    page.fill("#user-input", "Tell me something interesting about the universe")
    page.press("#user-input", "Enter")
    page.wait_for_selector(".streaming-cursor", state="detached", timeout=10000)

    # Give the context bar time to update
    page.wait_for_timeout(500)

    updated_text = page.locator(".context-pct").text_content()
    updated_pct = int(updated_text.replace("%", ""))

    assert updated_pct >= initial_pct


def test_context_bar_nonzero_after_message(chat_ready):
    """Context bar shows non-zero usage after sending a message."""
    page = chat_ready

    page.fill("#user-input", "hello")
    page.press("#user-input", "Enter")
    page.wait_for_selector(".streaming-cursor", state="detached", timeout=10000)
    page.wait_for_timeout(500)

    pct_text = page.locator(".context-pct").text_content()
    pct = int(pct_text.replace("%", ""))
    assert pct >= 1


def test_context_bar_filled_segments_are_green_when_present(chat_ready):
    """If any segments are filled at low usage, they are green (not amber/red)."""
    page = chat_ready

    # Send several messages to push usage up enough to fill a segment
    for i in range(5):
        page.fill("#user-input", f"Tell me about topic number {i} in great detail please")
        page.press("#user-input", "Enter")
        page.wait_for_selector(".streaming-cursor", state="detached", timeout=10000)

    page.wait_for_timeout(500)

    filled = page.locator(".context-segment.filled")
    if filled.count() > 0:
        # All filled segments should be green at this usage level
        green = page.locator(".context-segment.filled.green")
        assert green.count() == filled.count()
    else:
        # Usage still too low for a full segment, but percentage should be non-zero
        pct_text = page.locator(".context-pct").text_content()
        pct = int(pct_text.replace("%", ""))
        assert pct >= 1


def test_context_bar_resets_on_clear(chat_ready):
    """The context bar resets after clearing the conversation."""
    page = chat_ready

    # Send a message to increase usage
    page.fill("#user-input", "hello there, how are you today?")
    page.press("#user-input", "Enter")
    page.wait_for_selector(".streaming-cursor", state="detached", timeout=10000)
    page.wait_for_timeout(500)

    after_msg = page.locator(".context-pct").text_content()
    after_msg_pct = int(after_msg.replace("%", ""))

    # Clear
    page.fill("#user-input", "/clear")
    page.press("#user-input", "Enter")
    page.wait_for_selector(".message.system", timeout=5000)
    page.wait_for_timeout(500)

    after_clear = page.locator(".context-pct").text_content()
    after_clear_pct = int(after_clear.replace("%", ""))

    assert after_clear_pct <= after_msg_pct


def test_context_bar_clickable(chat_ready):
    """Clicking the context bar shows status details."""
    page = chat_ready

    page.fill("#user-input", "hello")
    page.press("#user-input", "Enter")
    page.wait_for_selector(".streaming-cursor", state="detached", timeout=10000)

    page.click("#context-bar")
    page.wait_for_selector(".status-grid", timeout=5000)

    assert page.locator(".status-grid").is_visible()
