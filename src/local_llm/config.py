from pathlib import Path

import yaml

_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"


def _load(filename: str) -> dict:
    path = _CONFIG_DIR / filename
    if path.exists():
        with open(path) as f:
            return yaml.safe_load(f) or {}
    return {}


_model = _load("model.yaml")
_general = _load("general.yaml")
_obsidian = _load("obsidian.yaml")

# Model config
DEFAULT_CONTEXT_TOKENS = _model.get("default_context_tokens", 4096)
TOKEN_ESTIMATE_RATIO = _model.get("token_estimate_ratio", 4.0)
CONTEXT_RESERVE = _model.get("context_reserve", 512)
SYSTEM_PROMPT = _model.get("system_prompt", "You are a helpful assistant.")
SUMMARY_MODEL = _model.get("summary_model", None)
SUMMARIZE_PROMPT = _model.get(
    "summarize_prompt",
    "Summarize the following conversation in under 200 words. "
    "Preserve key facts, decisions, and any instructions the user gave. "
    "Respond with only the summary, no preamble.",
)
TITLE_PROMPT = _model.get(
    "title_prompt",
    "Give this conversation a short title (under 8 words). "
    "Respond with only the title, no quotes or punctuation.",
)
TITLE_AFTER_EXCHANGES = _model.get("title_after_exchanges", 1)
MAX_INPUT_CHARS = _model.get("max_input_chars", 32000)

# General config
ARCHIVE_DIR = _general.get("archive_dir", "~/.local-llm/archives")

# Obsidian config
OBSIDIAN_ENABLED = _obsidian.get("enabled", False)
OBSIDIAN_VAULT_DIR = _obsidian.get("vault_dir", None)
OBSIDIAN_TAGS = _obsidian.get("tags", ["local-llm", "chat-archive"])
