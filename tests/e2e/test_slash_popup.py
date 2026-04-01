def test_slash_shows_popup(chat_ready):
    """Typing / shows the command popup with all commands."""
    page = chat_ready

    page.fill("#user-input", "/")
    popup = page.locator("#command-popup")
    assert popup.is_visible()

    items = page.locator(".command-item")
    assert items.count() == 3

    names = [items.nth(i).locator(".command-name").text_content() for i in range(3)]
    assert "/clear" in names
    assert "/model" in names
    assert "/status" in names


def test_slash_filters_commands(chat_ready):
    """Typing further filters the command list."""
    page = chat_ready

    page.fill("#user-input", "/cl")
    items = page.locator(".command-item")
    assert items.count() == 1
    assert items.first.locator(".command-name").text_content() == "/clear"


def test_slash_no_match_hides_popup(chat_ready):
    """Typing a non-matching prefix hides the popup."""
    page = chat_ready

    page.fill("#user-input", "/xyz")
    popup = page.locator("#command-popup")
    assert not popup.is_visible()


def test_arrow_keys_navigate(chat_ready):
    """Arrow keys move the highlight between commands."""
    page = chat_ready

    page.fill("#user-input", "/")
    page.wait_for_selector("#command-popup.visible")

    # First item highlighted by default
    items = page.locator(".command-item")
    assert "highlighted" in items.nth(0).get_attribute("class")

    # ArrowDown moves to second
    page.press("#user-input", "ArrowDown")
    assert "highlighted" in items.nth(1).get_attribute("class")
    assert "highlighted" not in items.nth(0).get_attribute("class")

    # ArrowUp moves back to first
    page.press("#user-input", "ArrowUp")
    assert "highlighted" in items.nth(0).get_attribute("class")


def test_enter_selects_command(chat_ready):
    """Enter executes the highlighted command."""
    page = chat_ready

    # Send a message first so /status has something to show
    page.fill("#user-input", "test")
    page.press("#user-input", "Enter")
    page.wait_for_selector(".streaming-cursor", state="detached", timeout=10000)

    # Now use the popup to trigger /status
    page.fill("#user-input", "/st")
    page.wait_for_selector("#command-popup.visible")
    page.press("#user-input", "Enter")

    # Popup should be gone
    popup = page.locator("#command-popup")
    assert not popup.is_visible()

    # Input should be empty
    assert page.input_value("#user-input") == ""

    # Status grid should appear in messages
    page.wait_for_selector(".status-grid", timeout=5000)


def test_escape_dismisses_popup(chat_ready):
    """Escape hides the popup and clears input."""
    page = chat_ready

    page.fill("#user-input", "/")
    page.wait_for_selector("#command-popup.visible")

    page.press("#user-input", "Escape")

    popup = page.locator("#command-popup")
    assert not popup.is_visible()
    assert page.input_value("#user-input") == ""


def test_click_selects_command(chat_ready):
    """Clicking a command item executes it."""
    page = chat_ready

    # Send a message first
    page.fill("#user-input", "test")
    page.press("#user-input", "Enter")
    page.wait_for_selector(".streaming-cursor", state="detached", timeout=10000)

    page.fill("#user-input", "/")
    page.wait_for_selector("#command-popup.visible")

    # Click /status
    status_item = page.locator(".command-item", has_text="/status")
    status_item.click()

    page.wait_for_selector(".status-grid", timeout=5000)


def test_tab_autocompletes(chat_ready):
    """Tab fills the input with the highlighted command name."""
    page = chat_ready

    page.fill("#user-input", "/cl")
    page.wait_for_selector("#command-popup.visible")

    page.press("#user-input", "Tab")
    assert page.input_value("#user-input") == "/clear"


def test_slash_mid_sentence_no_popup(chat_ready):
    """/ in the middle of text does not trigger the popup."""
    page = chat_ready

    page.fill("#user-input", "hello /clear")

    popup = page.locator("#command-popup")
    assert not popup.is_visible()
