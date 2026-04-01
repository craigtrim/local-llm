from local_llm.history import ConversationHistory


def test_stats_includes_tokens_remaining():
    h = ConversationHistory(4096)
    h.add("system", "You are helpful.")
    h.add("user", "hello")
    h.add("assistant", "hi")
    stats = h.stats()
    assert "tokens_remaining" in stats
    assert stats["tokens_remaining"] >= 0


def test_tokens_remaining_decreases_with_messages():
    h = ConversationHistory(4096)
    h.add("system", "You are helpful.")
    r1 = h.stats()["tokens_remaining"]

    h.add("user", "Tell me a long story about dragons and wizards.")
    r2 = h.stats()["tokens_remaining"]
    assert r2 < r1


def test_tokens_remaining_never_negative():
    h = ConversationHistory(100)
    h.add("system", "x" * 2000)
    assert h.stats()["tokens_remaining"] == 0


def test_pct_used_capped_at_100():
    h = ConversationHistory(1024)  # budget = 1024 - 512 = 512 tokens
    h.add("system", "x" * 4000)  # ~1000 tokens, well over budget
    assert h.stats()["pct_used"] == 100.0
