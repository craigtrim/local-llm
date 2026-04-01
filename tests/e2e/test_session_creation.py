def _select_first_assistant(page):
    """Click the first assistant card, handling the model subpicker if needed."""
    page.click(".assistant-card >> nth=0")
    subpicker = page.locator(".assistant-model-subpicker .model-option")
    try:
        subpicker.first.wait_for(timeout=2000)
        subpicker.first.click()
    except Exception:
        pass  # Assistant had a model bound, went straight to chat


def test_single_session_per_assistant_click(chat_page):
    """Clicking an assistant card creates exactly one session (#32)."""
    page = chat_page

    session_logs = []
    page.on("console", lambda msg: (
        session_logs.append(msg.text)
        if "Session created" in msg.text
        else None
    ))

    _select_first_assistant(page)

    page.wait_for_selector("#chat-container", state="visible")
    page.wait_for_timeout(500)

    created = [l for l in session_logs if "[selectAssistant] Session created:" in l]
    assert len(created) == 1, (
        f"Expected 1 session, got {len(created)}: {created}"
    )
