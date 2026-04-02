from .conftest import FAKE_RESPONSE


def test_click_archive_resumes_session(chat_ready, test_archive):
    """Clicking an archived conversation creates a resumed session with context."""
    page = chat_ready

    # Click the archive in the sidebar
    page.locator(".sidebar-recent-item").first.click()

    # Archived messages should appear in the chat
    page.wait_for_selector(".message.user", timeout=5000)
    user_msg = page.locator(".message.user").first
    assert "banana" in user_msg.text_content().lower()

    # Context bar should show non-zero usage (archived messages consume tokens)
    pct_text = page.locator(".context-pct").text_content()
    assert pct_text != "0%"

    # Send a follow-up message and verify the LLM responds
    page.fill("#user-input", "What was the code word?")
    page.press("#user-input", "Enter")
    page.wait_for_selector(".streaming-cursor", state="detached", timeout=10000)

    # Should have the original archived messages plus the new exchange
    user_msgs = page.locator(".message.user")
    assert user_msgs.count() == 2  # archived + new

    assistant_msgs = page.locator(".message.assistant")
    assert assistant_msgs.count() == 2  # archived + new response


def test_resumed_session_context_bar_reflects_history(chat_ready, test_archive):
    """After clicking an archive, context bar shows usage > 0%."""
    page = chat_ready

    page.locator(".sidebar-recent-item").first.click()
    page.wait_for_selector(".message.user", timeout=5000)

    # Wait for async context bar update to complete
    page.wait_for_function('document.querySelector(".context-pct").textContent !== "0%"', timeout=5000)
    pct = page.locator(".context-pct").text_content()
    assert pct != "0%"


def test_click_archive_then_clear_resets(chat_ready, test_archive):
    """Clearing after resume resets context to 0% and clears messages."""
    page = chat_ready

    page.locator(".sidebar-recent-item").first.click()
    page.wait_for_selector(".message.user", timeout=5000)

    # Clear
    page.click("#clear-btn")
    page.wait_for_selector(".message.system", timeout=5000)

    # Context should reset
    pct = page.locator(".context-pct").text_content()
    assert pct == "0%"

    # Only the system "Conversation cleared." message should remain
    user_msgs = page.locator(".message.user")
    assert user_msgs.count() == 0


def test_click_same_archive_twice_is_noop(chat_ready, test_archive):
    """Clicking the same archive again does not wipe new messages."""
    page = chat_ready

    # Resume the test archive
    page.locator(".sidebar-recent-item").first.click()
    page.wait_for_selector(".message.user", timeout=5000)

    # Send a new message
    page.fill("#user-input", "new message after resume")
    page.press("#user-input", "Enter")
    page.wait_for_selector(".streaming-cursor", state="detached", timeout=10000)

    # Record message count after sending
    msg_count = page.locator(".message.user").count()
    assert msg_count >= 2  # at least the archived msg + new one

    # Click the first sidebar item again (same archive, should be noop)
    page.wait_for_timeout(500)
    page.locator(".sidebar-recent-item").first.click()
    page.wait_for_timeout(500)

    # Message count should not change
    assert page.locator(".message.user").count() == msg_count


def test_switch_archive_saves_current_chat(chat_ready, test_archive):
    """Auto-save preserves current chat when switching to an archive."""
    page = chat_ready

    # Send a message (auto-save creates archive immediately)
    page.fill("#user-input", "unique save test message")
    page.press("#user-input", "Enter")
    page.wait_for_selector(".streaming-cursor", state="detached", timeout=10000)

    # Wait for auto-save to appear in sidebar
    page.wait_for_selector(".sidebar-recent-item", timeout=5000)
    count_after_send = page.locator(".sidebar-recent-item").count()
    assert count_after_send >= 2  # test_archive + auto-saved chat

    # Click an archived conversation (should NOT create a new archive)
    page.locator(".sidebar-recent-item").first.click()
    page.wait_for_selector(".message.user", timeout=5000)
    page.wait_for_timeout(500)

    # Count should not increase (auto-save already saved it)
    count_after_switch = page.locator(".sidebar-recent-item").count()
    assert count_after_switch == count_after_send
