import json
import logging
import re
from pathlib import Path

from .config import ASSISTANTS_DIR, SYSTEM_PROMPT

log = logging.getLogger("local_llm.assistants")

_REQUIRED_FIELDS = {"name", "model", "system_prompt"}
_OPTIONAL_FIELDS = {
    "description", "avatar_color", "context_tokens",
    "token_estimate_ratio", "context_reserve",
}
_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def _assistants_dir() -> Path:
    d = Path(ASSISTANTS_DIR).expanduser()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _slugify(text: str, max_len: int = 60) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_len].rstrip("-")


def _default_assistant() -> dict:
    return {
        "id": "default",
        "name": "Default",
        "description": "General-purpose assistant",
        "avatar_color": "#6b9fdb",
        "model": None,
        "system_prompt": SYSTEM_PROMPT,
        "context_tokens": None,
        "token_estimate_ratio": None,
        "context_reserve": None,
    }


def validate_assistant(config: dict) -> list[str]:
    errors: list[str] = []
    for field in _REQUIRED_FIELDS:
        if field == "model" and config.get("id") == "default":
            continue
        if not config.get(field):
            errors.append(f"'{field}' is required")

    color = config.get("avatar_color")
    if color and not _HEX_COLOR_RE.match(color):
        errors.append(f"'avatar_color' must be a hex color (e.g. #6b9fdb), got '{color}'")

    for num_field in ("context_tokens", "context_reserve"):
        val = config.get(num_field)
        if val is not None and (not isinstance(val, int) or val <= 0):
            errors.append(f"'{num_field}' must be a positive integer")

    ratio = config.get("token_estimate_ratio")
    if ratio is not None and (not isinstance(ratio, (int, float)) or ratio <= 0):
        errors.append("'token_estimate_ratio' must be a positive number")

    return errors


def list_assistants() -> list[dict]:
    d = _assistants_dir()
    default_on_disk = (d / "default.json").exists()
    results: list[dict] = []

    if not default_on_disk:
        results.append(_default_assistant())

    for f in sorted(d.glob("*.json")):
        try:
            config = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            log.warning("Skipping invalid assistant file: %s", f.name)
            continue
        config.setdefault("id", f.stem)
        results.append(config)

    # Ensure default is always first
    results.sort(key=lambda a: (0 if a.get("id") == "default" else 1, a.get("name", "")))
    return results


def get_assistant(assistant_id: str) -> dict | None:
    if assistant_id == "default":
        path = _assistants_dir() / "default.json"
        if path.exists():
            try:
                config = json.loads(path.read_text())
                config.setdefault("id", "default")
                return config
            except (json.JSONDecodeError, OSError):
                pass
        return _default_assistant()

    path = _assistants_dir() / f"{assistant_id}.json"
    if not path.exists():
        return None
    try:
        config = json.loads(path.read_text())
        config.setdefault("id", assistant_id)
        return config
    except (json.JSONDecodeError, OSError):
        return None


def save_assistant(config: dict) -> dict:
    if "id" not in config or not config["id"]:
        config["id"] = _slugify(config.get("name", "unnamed"))

    errors = validate_assistant(config)
    if errors:
        raise ValueError("; ".join(errors))

    path = _assistants_dir() / f"{config['id']}.json"
    with open(path, "w") as f:
        json.dump(config, f, indent=2)

    log.info("Saved assistant: %s (%s)", config["id"], config.get("name"))
    return config


def delete_assistant(assistant_id: str) -> bool:
    if assistant_id == "default":
        raise ValueError("Cannot delete the default assistant")

    path = _assistants_dir() / f"{assistant_id}.json"
    if not path.exists():
        return False
    path.unlink()
    log.info("Deleted assistant: %s", assistant_id)
    return True
