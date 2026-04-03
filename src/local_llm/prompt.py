"""System prompt wrapping with behavioral guardrails (#57)."""

from .config import SYSTEM_PROMPT_WRAPPER


def wrap_system_prompt(raw_prompt: str, enable: bool = True) -> str:
    """Wrap a raw system prompt with behavioral guardrails.

    Returns the raw prompt unchanged if wrapping is disabled
    or no wrapper template is configured.
    """
    if not enable or not SYSTEM_PROMPT_WRAPPER:
        return raw_prompt
    return SYSTEM_PROMPT_WRAPPER.format(user_prompt=raw_prompt)
