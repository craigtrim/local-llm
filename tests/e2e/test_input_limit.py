"""Tests for input length limiting in the web UI."""


def test_status_includes_max_input_chars(chat_ready):
    """The status endpoint returns a max_input_chars field."""
    page = chat_ready
    session_id = page.evaluate("""() => sessionId""")
    resp = page.evaluate(
        """(sid) => fetch(`/api/sessions/${sid}/status`).then(r => r.json())""",
        session_id,
    )
    assert "max_input_chars" in resp
    assert resp["max_input_chars"] > 0


def test_no_counter_on_short_input(chat_ready):
    """Counter is hidden for normal short messages."""
    page = chat_ready
    page.fill("#user-input", "hello")
    hint = page.locator("#input-hint")
    assert "chars" not in hint.text_content()
    assert not page.locator("#send-btn").is_disabled()


def test_counter_appears_at_half_limit(chat_ready):
    """Character counter appears when input exceeds 50% of limit."""
    page = chat_ready

    # Get the current limit from JS
    limit = page.evaluate("""() => maxInputChars""")
    half_text = "a" * int(limit * 0.55)
    page.fill("#user-input", half_text)

    hint = page.locator("#input-hint")
    assert "chars" in hint.text_content()
    assert not page.locator("#send-btn").is_disabled()


def test_send_disabled_over_limit(chat_ready):
    """Send button is disabled when input exceeds the limit."""
    page = chat_ready

    limit = page.evaluate("""() => maxInputChars""")
    over_text = "a" * (limit + 100)
    page.fill("#user-input", over_text)

    hint = page.locator("#input-hint")
    assert "too long" in hint.text_content().lower()
    assert page.locator("#send-btn").is_disabled()


def test_send_re_enabled_after_trimming(chat_ready):
    """Send button re-enables after user trims text back under the limit."""
    page = chat_ready

    limit = page.evaluate("""() => maxInputChars""")
    over_text = "a" * (limit + 100)
    page.fill("#user-input", over_text)
    assert page.locator("#send-btn").is_disabled()

    # Trim back to short text
    page.fill("#user-input", "hello")
    assert not page.locator("#send-btn").is_disabled()
    assert "chars" not in page.locator("#input-hint").text_content()
