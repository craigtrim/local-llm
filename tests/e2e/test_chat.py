from .conftest import FAKE_RESPONSE


def test_send_message_and_receive_response(chat_ready):
    """Sending a message produces a user bubble and a streamed assistant response."""
    page = chat_ready

    page.fill("#user-input", "hello")
    page.press("#user-input", "Enter")

    # User message should appear
    user_msg = page.locator(".message.user")
    user_msg.wait_for(state="visible")
    assert "hello" in user_msg.text_content()

    # Assistant message should stream in and complete (exclude greeting)
    assistant_msg = page.locator(".message.assistant:not(.greeting)")
    assistant_msg.wait_for(state="visible")

    # Wait for streaming to finish (cursor disappears)
    page.wait_for_selector(".streaming-cursor", state="detached", timeout=10000)

    # Verify response content
    content = assistant_msg.locator(".message-content").text_content()
    assert "test assistant" in content.lower()


def test_shift_enter_adds_newline(chat_ready):
    """Shift+Enter inserts a newline instead of sending."""
    page = chat_ready

    page.click("#user-input")
    page.keyboard.type("line1")
    page.keyboard.press("Shift+Enter")
    page.keyboard.type("line2")

    value = page.input_value("#user-input")
    assert "line1" in value
    assert "line2" in value

    # No messages should have been sent (greeting may exist)
    messages = page.locator(".message:not(.greeting)")
    assert messages.count() == 0


def test_empty_input_not_sent(chat_ready):
    """Pressing Enter with empty input does nothing."""
    page = chat_ready

    page.press("#user-input", "Enter")

    messages = page.locator(".message:not(.greeting)")
    assert messages.count() == 0


def test_multiple_messages(chat_ready):
    """Can send multiple messages in sequence."""
    page = chat_ready

    page.fill("#user-input", "first message")
    page.press("#user-input", "Enter")
    page.wait_for_selector(".streaming-cursor", state="detached", timeout=10000)

    page.fill("#user-input", "second message")
    page.press("#user-input", "Enter")
    page.wait_for_selector(".streaming-cursor", state="detached", timeout=10000)

    user_msgs = page.locator(".message.user")
    assert user_msgs.count() == 2

    assistant_msgs = page.locator(".message.assistant:not(.greeting)")
    assert assistant_msgs.count() == 2
