def test_favicon_link_exists(chat_page):
    """The page must have a favicon link tag (#39)."""
    favicon = chat_page.locator("link[rel='icon']")
    assert favicon.count() == 1
    href = favicon.get_attribute("href")
    assert href and "svg" in href
