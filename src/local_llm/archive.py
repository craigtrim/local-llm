import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from .config import ARCHIVE_DIR

log = logging.getLogger("local_llm.archive")

_VALID_ROLES = {"system", "user", "assistant"}


def _slugify(text: str, max_len: int = 60) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_len].rstrip("-")


def validate_archive(data: object, filename: str | None = None) -> list[str]:
    """Validate parsed archive JSON. Returns list of error strings (empty = valid)."""
    prefix = f"{filename}: " if filename else ""
    errors: list[str] = []

    if not isinstance(data, dict):
        errors.append(f"{prefix}expected dict, got {type(data).__name__}")
        return errors

    if "title" not in data:
        errors.append(f"{prefix}missing 'title' key")
    elif data["title"] is not None and not isinstance(data["title"], str):
        errors.append(f"{prefix}'title' must be a string or null, got {type(data['title']).__name__}")

    if "messages" not in data:
        errors.append(f"{prefix}missing 'messages' key")
        return errors

    messages = data["messages"]
    if not isinstance(messages, list):
        errors.append(f"{prefix}'messages' must be a list, got {type(messages).__name__}")
        return errors

    for i, msg in enumerate(messages):
        if not isinstance(msg, dict):
            errors.append(f"{prefix}messages[{i}] must be a dict, got {type(msg).__name__}")
            continue
        if "role" not in msg:
            errors.append(f"{prefix}messages[{i}] missing 'role' key")
        elif msg["role"] not in _VALID_ROLES:
            errors.append(f"{prefix}messages[{i}] has invalid role '{msg['role']}'")
        if "content" not in msg:
            errors.append(f"{prefix}messages[{i}] missing 'content' key")
        elif not isinstance(msg["content"], str):
            errors.append(f"{prefix}messages[{i}] 'content' must be a string, got {type(msg['content']).__name__}")

    has_non_system = any(
        isinstance(m, dict) and m.get("role") in ("user", "assistant")
        for m in messages
    )
    if not has_non_system:
        errors.append(f"{prefix}no user or assistant messages found")

    return errors


def save(messages: list[dict], title: str | None = None) -> Path | None:
    if len(messages) <= 1:
        return None

    archive_dir = Path(ARCHIVE_DIR).expanduser()
    archive_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    suffix = f"_{_slugify(title)}" if title else ""
    path = archive_dir / f"{timestamp}{suffix}.json"

    data = {"title": title, "messages": messages}
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

    return path


def list_archives(limit: int = 50) -> list[dict]:
    """Return recent archives as [{filename, title, timestamp}, ...]."""
    archive_dir = Path(ARCHIVE_DIR).expanduser()
    if not archive_dir.exists():
        return []
    files = sorted(archive_dir.glob("*.json"), reverse=True)[:limit]
    results = []
    for f in files:
        try:
            data = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        errors = validate_archive(data, f.name)
        if errors:
            log.warning("Skipping invalid archive %s: %s", f.name, "; ".join(errors))
            continue
        messages = data.get("messages", [])
        title = data.get("title") or next(
            (m["content"][:80] for m in messages if m["role"] == "user"),
            "Untitled",
        )
        results.append({
            "filename": f.name,
            "title": title,
            "timestamp": f.stem.split("_")[0] if "_" in f.stem else f.stem,
        })
    return results


def delete_archive(filename: str) -> bool:
    """Delete a specific archive file. Returns True if deleted, False if not found."""
    archive_dir = Path(ARCHIVE_DIR).expanduser()
    path = archive_dir / filename
    if not path.exists() or not path.is_relative_to(archive_dir):
        return False
    path.unlink()
    return True


def load_archive(filename: str) -> list[dict]:
    """Load messages from a specific archive file."""
    archive_dir = Path(ARCHIVE_DIR).expanduser()
    path = archive_dir / filename
    if not path.exists() or not path.is_relative_to(archive_dir):
        return []
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    errors = validate_archive(data, filename)
    if errors:
        log.warning("Invalid archive %s: %s", filename, "; ".join(errors))
        return []
    return data.get("messages", [])
