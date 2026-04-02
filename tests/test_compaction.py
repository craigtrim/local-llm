"""Tests for conversation compaction (#51)."""

from local_llm.history import ConversationHistory


def _make_history(limit=200, **kw):
    return ConversationHistory(context_limit=limit, context_reserve=20, **kw)


def _fake_summarize(msgs):
    return f"Summary of {len(msgs)} messages"


def test_compaction_triggers_at_budget():
    """When messages exceed budget, compaction fires and shrinks _messages."""
    h = _make_history(limit=200, summarize_fn=_fake_summarize)
    h.add("system", "You help.")
    # Fill up context
    for i in range(20):
        h.add("user", f"question {i} " * 10)
        h.add("assistant", f"answer {i} " * 10)

    before = len(h._messages)
    h.get_messages()  # triggers compaction
    after = len(h._messages)
    assert after < before, f"Messages not compacted: {before} -> {after}"


def test_compacted_messages_replaced_with_summary():
    """After compaction, a summary message exists in _messages."""
    h = _make_history(limit=200, summarize_fn=_fake_summarize)
    h.add("system", "You help.")
    for i in range(20):
        h.add("user", f"q{i} " * 10)
        h.add("assistant", f"a{i} " * 10)

    h.get_messages()
    summaries = [m for m in h._messages if m.get("type") == "summary"]
    assert len(summaries) >= 1
    assert "Summary of" in summaries[0]["content"]


def test_stats_reflect_freed_tokens():
    """After compaction, tokens_used should decrease."""
    h = _make_history(limit=500, summarize_fn=_fake_summarize)
    h.add("system", "You help.")
    for i in range(30):
        h.add("user", f"question {i} " * 10)
        h.add("assistant", f"answer {i} " * 10)

    tokens_before = h.stats()["tokens_used"]
    h.get_messages()  # triggers compaction
    tokens_after = h.stats()["tokens_used"]
    assert tokens_after < tokens_before, f"Tokens not freed: {tokens_before} -> {tokens_after}"


def test_multiple_compactions():
    """Filling context again after compaction produces a second summary."""
    h = _make_history(limit=200, summarize_fn=_fake_summarize)
    h.add("system", "You help.")

    # First fill
    for i in range(20):
        h.add("user", f"q{i} " * 10)
        h.add("assistant", f"a{i} " * 10)
    h.get_messages()

    # Second fill
    for i in range(20):
        h.add("user", f"q2_{i} " * 10)
        h.add("assistant", f"a2_{i} " * 10)
    h.get_messages()

    summaries = [m for m in h._messages if m.get("type") == "summary"]
    assert len(summaries) >= 1  # at least one summary present


def test_summary_has_correct_fields():
    """Summary message has type, evicted_count, and timestamp."""
    h = _make_history(limit=200, summarize_fn=_fake_summarize)
    h.add("system", "You help.")
    for i in range(20):
        h.add("user", f"q{i} " * 10)
        h.add("assistant", f"a{i} " * 10)

    h.get_messages()
    summary = next(m for m in h._messages if m.get("type") == "summary")
    assert summary["role"] == "system"
    assert summary["type"] == "summary"
    assert summary["evicted_count"] > 0
    assert "timestamp" in summary


def test_get_messages_strips_extra_fields():
    """get_messages returns only role+content for Ollama compatibility."""
    h = _make_history(limit=200, summarize_fn=_fake_summarize)
    h.add("system", "You help.")
    for i in range(20):
        h.add("user", f"q{i} " * 10)
        h.add("assistant", f"a{i} " * 10)

    msgs = h.get_messages()
    for m in msgs:
        assert set(m.keys()) == {"role", "content"}, f"Extra keys in message: {m.keys()}"
