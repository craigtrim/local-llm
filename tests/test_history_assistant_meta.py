"""Tests for per-message assistant metadata in ConversationHistory (#30)."""

from local_llm.history import ConversationHistory


def _make_history(**kw):
    return ConversationHistory(context_limit=4096, **kw)


def test_assistant_message_includes_uuid():
    h = _make_history(assistant_uuid="abc123", assistant_name="Bot")
    h.add("assistant", "hello")
    assert h.messages[-1]["assistant_uuid"] == "abc123"


def test_assistant_message_includes_name():
    h = _make_history(assistant_uuid="abc123", assistant_name="Bot")
    h.add("assistant", "hello")
    assert h.messages[-1]["assistant_name"] == "Bot"


def test_user_message_no_assistant_fields():
    h = _make_history(assistant_uuid="abc123", assistant_name="Bot")
    h.add("user", "hi")
    msg = h.messages[-1]
    assert "assistant_uuid" not in msg
    assert "assistant_name" not in msg


def test_system_message_no_assistant_fields():
    h = _make_history(assistant_uuid="abc123", assistant_name="Bot")
    h.add("system", "You are helpful.")
    msg = h.messages[-1]
    assert "assistant_uuid" not in msg
    assert "assistant_name" not in msg


def test_history_without_assistant_uuid():
    h = _make_history()
    h.add("assistant", "hello")
    msg = h.messages[-1]
    assert "assistant_uuid" not in msg
    assert "assistant_name" not in msg


def test_messages_property_includes_metadata():
    h = _make_history(assistant_uuid="xyz", assistant_name="Helper")
    h.add("user", "q")
    h.add("assistant", "a")
    msgs = h.messages
    assert msgs[1]["assistant_uuid"] == "xyz"
    assert "assistant_uuid" not in msgs[0]


def test_get_messages_strips_metadata():
    """get_messages() returns only role/content for Ollama compatibility."""
    h = _make_history(assistant_uuid="xyz", assistant_name="Helper")
    h.add("user", "q")
    h.add("assistant", "a")
    msgs = h.get_messages()
    for m in msgs:
        assert set(m.keys()) == {"role", "content"}


def test_stats_unaffected_by_metadata():
    h = _make_history(assistant_uuid="xyz", assistant_name="Helper")
    h.add("user", "hello")
    h.add("assistant", "hi there")
    stats = h.stats()
    # Token count should only be based on content, not metadata field names
    assert stats["tokens_used"] > 0
    assert stats["qa_count"] == 1
