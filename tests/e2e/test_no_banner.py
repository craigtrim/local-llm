def test_no_assistant_banner_in_html(chat_ready):
    """The assistant banner strip must not exist in the DOM."""
    assert chat_ready.locator("#assistant-banner").count() == 0
