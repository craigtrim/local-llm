"""Unit tests for system prompt wrapping (#57)."""

from unittest.mock import patch


FAKE_WRAPPER = "{user_prompt}\n\n## Guidelines\n- Be direct."


def test_wrap_applies_template():
    """Wrapper template is applied around the raw prompt."""
    with patch("local_llm.prompt.SYSTEM_PROMPT_WRAPPER", FAKE_WRAPPER):
        from local_llm.prompt import wrap_system_prompt
        result = wrap_system_prompt("You are a helpful bot.")
    assert "You are a helpful bot." in result
    assert "## Guidelines" in result


def test_wrap_disabled_returns_raw():
    """enable=False returns the raw prompt unchanged."""
    with patch("local_llm.prompt.SYSTEM_PROMPT_WRAPPER", FAKE_WRAPPER):
        from local_llm.prompt import wrap_system_prompt
        result = wrap_system_prompt("You are a helpful bot.", enable=False)
    assert result == "You are a helpful bot."


def test_wrap_no_template_returns_raw():
    """When SYSTEM_PROMPT_WRAPPER is None, returns raw prompt unchanged."""
    with patch("local_llm.prompt.SYSTEM_PROMPT_WRAPPER", None):
        from local_llm.prompt import wrap_system_prompt
        result = wrap_system_prompt("You are a helpful bot.")
    assert result == "You are a helpful bot."


def test_wrap_preserves_raw_prompt_verbatim():
    """The full original prompt text appears inside the wrapped output."""
    raw = (
        "You are an air fryer cooking assistant specialized exclusively "
        "in the Ninja DoubleStack Air Fryer (models SL201, SL401, SL451)."
    )
    with patch("local_llm.prompt.SYSTEM_PROMPT_WRAPPER", FAKE_WRAPPER):
        from local_llm.prompt import wrap_system_prompt
        result = wrap_system_prompt(raw)
    assert raw in result
