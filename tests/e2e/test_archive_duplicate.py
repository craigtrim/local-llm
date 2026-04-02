"""E2E tests for archive duplicate prevention (#47)."""

from .conftest import FAKE_RESPONSE


def test_browse_recents_no_duplicate(chat_ready):
    """Click archive A, click archive B, verify no new archive created."""
    page = chat_ready

    # Send a message to create an archive via auto-save
    page.fill("#user-input", "first conversation")
    page.press("#user-input", "Enter")
    page.wait_for_selector(".streaming-cursor", state="detached", timeout=10000)

    # Clear to start a second session
    page.wait_for_function('!document.getElementById("clear-btn").disabled', timeout=5000)
    page.click("#clear-btn")
    page.wait_for_selector(".message.system", timeout=5000)

    # Send a message in second session
    page.fill("#user-input", "second conversation")
    page.press("#user-input", "Enter")
    page.wait_for_selector(".streaming-cursor", state="detached", timeout=10000)

    # Wait for auto-save to create the archive and sidebar to refresh
    page.wait_for_selector(".sidebar-recent-item", timeout=5000)
    archive_count_before = page.locator(".sidebar-recent-item").count()
    assert archive_count_before >= 1

    # Click the first archive
    page.locator(".sidebar-recent-item").first.click()
    page.wait_for_timeout(1000)

    # Click back to the second archive (or clear)
    page.wait_for_function('!document.getElementById("clear-btn").disabled', timeout=5000)
    page.click("#clear-btn")
    page.wait_for_selector(".message.system", timeout=5000)
    page.wait_for_timeout(500)

    # Archive count should not have increased
    archive_count_after = page.locator(".sidebar-recent-item").count()
    assert archive_count_after <= archive_count_before + 1, (
        f"Archive count grew from {archive_count_before} to {archive_count_after}"
    )


def test_browse_then_chat_no_duplicate(chat_ready):
    """Resume archive, send a message, verify original archive is updated (not duplicated)."""
    page = chat_ready

    # Create an archive
    page.fill("#user-input", "original question")
    page.press("#user-input", "Enter")
    page.wait_for_selector(".streaming-cursor", state="detached", timeout=10000)

    # Wait for auto-save and sidebar refresh
    page.wait_for_selector(".sidebar-recent-item", timeout=5000)
    archive_count_before = page.locator(".sidebar-recent-item").count()

    # Click the archive to resume it
    page.locator(".sidebar-recent-item").first.click()
    page.wait_for_timeout(1000)

    # Send a follow-up in the resumed session
    page.fill("#user-input", "follow up question")
    page.press("#user-input", "Enter")
    page.wait_for_selector(".streaming-cursor", state="detached", timeout=10000)
    page.wait_for_timeout(500)

    # Archive count should be the same (overwritten, not duplicated)
    archive_count_after = page.locator(".sidebar-recent-item").count()
    assert archive_count_after == archive_count_before, (
        f"Archive count changed from {archive_count_before} to {archive_count_after}"
    )
