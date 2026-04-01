import pytest

try:
    import ollama as ollama_lib
    _models = ollama_lib.list()
    # Skip embedding-only models (they don't support chat)
    _CHAT_MODEL = None
    for m in _models.models:
        if "embed" not in m.model:
            _CHAT_MODEL = m.model
            break
    _OLLAMA_AVAILABLE = _CHAT_MODEL is not None
except Exception:
    _OLLAMA_AVAILABLE = False
    _CHAT_MODEL = None

pytestmark = pytest.mark.skipif(not _OLLAMA_AVAILABLE, reason="Ollama not running")


def test_get_messages_produces_ollama_compatible_keys():
    """get_messages() must return only keys that the Ollama API accepts."""
    from local_llm.history import ConversationHistory

    h = ConversationHistory(context_limit=4096)
    h.add("system", "You are a test assistant.")
    h.add("user", "Say hello in one word.")
    messages = h.get_messages()

    allowed = {"role", "content", "images"}
    for msg in messages:
        unexpected = set(msg.keys()) - allowed
        assert not unexpected, f"Unexpected keys in message for Ollama: {unexpected}"


def test_real_ollama_chat_accepts_message_format():
    """Messages from get_messages() must be accepted by a real Ollama model."""
    from local_llm.history import ConversationHistory

    h = ConversationHistory(context_limit=4096)
    h.add("system", "You are a test assistant.")
    h.add("user", "Say hello in one word.")
    messages = h.get_messages()

    response = ollama_lib.chat(model=_CHAT_MODEL, messages=messages)
    assert response["message"]["content"]


def test_real_ollama_streaming_accepts_message_format():
    """Streaming mode must also work with messages from get_messages()."""
    from local_llm.history import ConversationHistory

    h = ConversationHistory(context_limit=4096)
    h.add("system", "You are a test assistant.")
    h.add("user", "Say hello in one word.")
    messages = h.get_messages()

    tokens = []
    for chunk in ollama_lib.chat(model=_CHAT_MODEL, messages=messages, stream=True):
        token = chunk.get("message", {}).get("content", "")
        if token:
            tokens.append(token)

    assert len(tokens) > 0, "Streaming produced zero tokens"
