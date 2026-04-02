import json
import logging

import ollama

from .config import DEFAULT_CONTEXT_TOKENS, GREETING_COUNT, GREETING_PROMPT

log = logging.getLogger("local_llm.client")


def list_models() -> list[str]:
    try:
        response = ollama.list()
        return sorted(model.model for model in response.models)
    except Exception:
        return []


def get_context_length(model: str) -> int:
    try:
        info = ollama.show(model)
        model_info = info.get("model_info", {})
        for key, value in model_info.items():
            if key.endswith(".context_length") and isinstance(value, int):
                return value
    except Exception:
        pass
    return DEFAULT_CONTEXT_TOKENS


def chat(model: str, messages: list[dict]) -> str:
    response = ollama.chat(model=model, messages=messages)
    return response["message"]["content"]


def summarize(messages: list[dict], model: str, prompt: str) -> str:
    formatted = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
    return chat(model, [
        {"role": "system", "content": prompt},
        {"role": "user", "content": formatted},
    ])


def generate_title(messages: list[dict], model: str, prompt: str) -> str:
    formatted = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
    title = chat(model, [
        {"role": "system", "content": prompt},
        {"role": "user", "content": formatted},
    ])
    return title.strip().strip("\"'.")


def generate_greetings(name: str, system_prompt: str, model: str, count: int | None = None) -> list[str]:
    """Generate greeting variations for an assistant using an LLM."""
    count = count or GREETING_COUNT
    prompt = GREETING_PROMPT.format(name=name, system_prompt=system_prompt, count=count)
    try:
        raw = chat(model, [{"role": "user", "content": prompt}])
        # Parse the JSON array from the response
        # Strip markdown fences if present
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            text = text.rsplit("```", 1)[0]
        greetings = json.loads(text)
        if isinstance(greetings, list) and all(isinstance(g, str) for g in greetings):
            # Filter empty strings
            greetings = [g.strip() for g in greetings if g.strip()]
            log.info("Generated %d greetings for %s", len(greetings), name)
            return greetings[:count]
    except Exception as e:
        log.warning("Failed to generate greetings for %s: %s", name, e)
    return []
