import ollama

from .config import DEFAULT_CONTEXT_TOKENS


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
