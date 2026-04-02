"""E2E tests for sidebar active conversation highlight (#49)."""

from playwright.sync_api import expect


def test_active_archive_highlighted(chat_ready, test_archive):
    """Clicking a Recents item gives it the active class."""
    page = chat_ready
    item = page.locator(".sidebar-recent-item").first
    item.click()
    page.wait_for_selector(".message.user", timeout=5000)
    # After loadArchives refreshes, the clicked item should be active
    page.wait_for_timeout(500)
    active = page.locator(".sidebar-recent-item.active")
    expect(active).to_have_count(1)


def test_highlight_moves_on_switch(chat_ready, test_archive):
    """Switching to a different archive moves the highlight."""
    page = chat_ready

    # Send a message to create a second archive via auto-save
    page.fill("#user-input", "create second archive")
    page.press("#user-input", "Enter")
    page.wait_for_selector(".streaming-cursor", state="detached", timeout=10000)
    page.wait_for_timeout(500)

    # Should have at least 2 sidebar items
    items = page.locator(".sidebar-recent-item")
    assert items.count() >= 2

    # Click the second item
    items.nth(1).click()
    page.wait_for_timeout(1000)

    # Only one item should be active
    active = page.locator(".sidebar-recent-item.active")
    expect(active).to_have_count(1)


def test_new_session_highlights_after_first_message(chat_ready):
    """A fresh session gets highlighted in sidebar after the first message."""
    page = chat_ready

    # No active item initially
    active_before = page.locator(".sidebar-recent-item.active").count()

    # Send a message (auto-save creates archive, sidebar refreshes)
    page.fill("#user-input", "hello")
    page.press("#user-input", "Enter")
    page.wait_for_selector(".streaming-cursor", state="detached", timeout=10000)
    page.wait_for_timeout(500)

    # Now there should be an active item
    active = page.locator(".sidebar-recent-item.active")
    expect(active).to_have_count(1)


def test_clear_removes_highlight(chat_ready):
    """After /clear, no sidebar item should be highlighted (new empty session)."""
    page = chat_ready

    # Send a message to create an archive
    page.fill("#user-input", "test")
    page.press("#user-input", "Enter")
    page.wait_for_selector(".streaming-cursor", state="detached", timeout=10000)
    page.wait_for_function('!document.getElementById("clear-btn").disabled', timeout=5000)

    # Clear
    page.click("#clear-btn")
    page.wait_for_selector(".message.system", timeout=5000)
    page.wait_for_timeout(500)

    # No active item (new session has no archive yet)
    active = page.locator(".sidebar-recent-item.active")
    expect(active).to_have_count(0)
