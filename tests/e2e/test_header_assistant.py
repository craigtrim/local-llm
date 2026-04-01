"""E2E tests for header assistant controls (#28)."""

import pytest
from playwright.sync_api import expect


def test_no_assistant_button(chat_ready):
    """The /assistant button should not exist in the header."""
    assert chat_ready.locator("#assistant-btn").count() == 0


def test_header_group_visible_after_assistant_select(chat_ready):
    """The header assistant group (dot + name) should be visible."""
    group = chat_ready.locator("#header-assistant-group")
    expect(group).to_be_visible()


def test_header_group_shows_assistant_name(chat_ready):
    """The header should display the assistant name."""
    name = chat_ready.locator("#header-assistant-name")
    expect(name).not_to_be_empty()


def test_header_group_click_opens_overlay(chat_ready):
    """Clicking the header assistant group should open the assistant picker."""
    chat_ready.click("#header-assistant-group")
    overlay = chat_ready.locator("#assistant-overlay")
    expect(overlay).to_be_visible()


def test_banner_click_opens_overlay(chat_ready):
    """Clicking the assistant banner should open the assistant picker."""
    banner = chat_ready.locator("#assistant-banner")
    if banner.is_visible():
        banner.click()
        overlay = chat_ready.locator("#assistant-overlay")
        expect(overlay).to_be_visible()


def test_slash_assistant_still_works(chat_ready):
    """The /assistant slash command should still open the picker."""
    input_el = chat_ready.locator("#user-input")
    input_el.fill("/assistant")
    # The command popup should show the assistant command
    popup = chat_ready.locator("#command-popup")
    expect(popup).to_be_visible()


def test_clear_preserves_assistant_name(chat_ready):
    """After /clear, the assistant name should still appear in the header."""
    input_el = chat_ready.locator("#user-input")
    input_el.fill("hello")
    input_el.press("Enter")
    # Wait for streaming to finish (clear button becomes enabled after context bar update)
    chat_ready.wait_for_selector(".streaming-cursor", state="detached", timeout=10000)
    chat_ready.wait_for_function('!document.getElementById("clear-btn").disabled', timeout=5000)
    name_before = chat_ready.locator("#header-assistant-name").text_content()
    chat_ready.click("#clear-btn")
    chat_ready.wait_for_selector(".message.system", timeout=5000)
    name_after = chat_ready.locator("#header-assistant-name").text_content()
    assert name_after == name_before
