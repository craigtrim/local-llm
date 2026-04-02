import json
import logging
import re
import uuid as uuid_mod
from datetime import datetime, timezone
from pathlib import Path

from .config import ASSISTANTS_DIR, SYSTEM_PROMPT

# Fields that affect greeting content; changes trigger regeneration
_GREETING_TRIGGER_FIELDS = {"name", "model", "system_prompt"}

log = logging.getLogger("local_llm.assistants")

_REQUIRED_FIELDS = {"name", "model", "system_prompt"}
_OPTIONAL_FIELDS = {
    "description", "avatar_color", "context_tokens",
    "token_estimate_ratio", "context_reserve",
}
_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_UUID_RE = re.compile(r"^[0-9a-f]{32}$")

# Stable UUID for the built-in default assistant (survives across installs)
_DEFAULT_UUID = "00000000000000000000000000000000"


def _assistants_dir() -> Path:
    d = Path(ASSISTANTS_DIR).expanduser()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _history_dir() -> Path:
    d = _assistants_dir() / "history"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _slugify(text: str, max_len: int = 60) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_len].rstrip("-")


def _generate_uuid() -> str:
    return uuid_mod.uuid4().hex


def _default_assistant() -> dict:
    return {
        "id": "default",
        "uuid": _DEFAULT_UUID,
        "name": "Default",
        "description": "General-purpose assistant",
        "avatar_color": "#6b9fdb",
        "model": None,
        "system_prompt": SYSTEM_PROMPT,
        "context_tokens": None,
        "token_estimate_ratio": None,
        "context_reserve": None,
        "version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _migrate(config: dict) -> bool:
    """Add uuid/version/created_at to legacy configs. Returns True if modified."""
    changed = False
    if "uuid" not in config:
        config["uuid"] = _DEFAULT_UUID if config.get("id") == "default" else _generate_uuid()
        changed = True
    if "version" not in config:
        config["version"] = 1
        changed = True
    if "created_at" not in config:
        config["created_at"] = datetime.now(timezone.utc).isoformat()
        changed = True
    return changed


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

    uid = config.get("uuid")
    if uid is not None and not _UUID_RE.match(uid):
        errors.append(f"'uuid' must be 32 hex characters, got '{uid}'")

    version = config.get("version")
    if version is not None and (not isinstance(version, int) or version < 1):
        errors.append("'version' must be a positive integer")

    return errors


def _load_and_migrate(path: Path, fallback_id: str | None = None) -> dict | None:
    """Load a JSON assistant file, apply migration if needed, return config."""
    try:
        config = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    if fallback_id:
        config.setdefault("id", fallback_id)
    if _migrate(config):
        try:
            with open(path, "w") as f:
                json.dump(config, f, indent=2)
        except OSError:
            pass
    return config


def list_assistants() -> list[dict]:
    d = _assistants_dir()
    default_on_disk = (d / "default.json").exists()
    results: list[dict] = []

    if not default_on_disk:
        results.append(_default_assistant())

    for f in sorted(d.glob("*.json")):
        config = _load_and_migrate(f, fallback_id=f.stem)
        if config is None:
            log.warning("Skipping invalid assistant file: %s", f.name)
            continue
        results.append(config)

    results.sort(key=lambda a: (0 if a.get("id") == "default" else 1, a.get("name", "")))
    return results


def get_assistant(assistant_id: str) -> dict | None:
    if assistant_id == "default":
        path = _assistants_dir() / "default.json"
        if path.exists():
            config = _load_and_migrate(path, fallback_id="default")
            if config:
                return config
        return _default_assistant()

    path = _assistants_dir() / f"{assistant_id}.json"
    if not path.exists():
        return None
    return _load_and_migrate(path, fallback_id=assistant_id)


def get_assistant_by_uuid(target_uuid: str) -> dict | None:
    """Find an assistant by UUID, regardless of current slug/ID."""
    for f in _assistants_dir().glob("*.json"):
        config = _load_and_migrate(f, fallback_id=f.stem)
        if config and config.get("uuid") == target_uuid:
            return config
    # Check in-memory default
    if target_uuid == _DEFAULT_UUID:
        return _default_assistant()
    return None


def _needs_greeting_regen(existing: dict | None, config: dict) -> bool:
    """Check if greeting-triggering fields changed."""
    if not existing:
        return True  # New assistant, always generate
    if not existing.get("greetings"):
        return True  # No greetings yet
    for field in _GREETING_TRIGGER_FIELDS:
        if existing.get(field) != config.get(field):
            return True
    return False


def save_assistant(config: dict, generate_greetings_fn=None) -> dict:
    if "id" not in config or not config["id"]:
        config["id"] = _slugify(config.get("name", "unnamed"))

    current_id = config["id"]

    # Load existing to preserve UUID and handle versioning
    existing = None
    old_path = _assistants_dir() / f"{current_id}.json"
    if old_path.exists():
        existing = _load_and_migrate(old_path, fallback_id=current_id)

    # Preserve UUID from existing, or generate new
    if existing and existing.get("uuid"):
        config["uuid"] = existing["uuid"]
        config["created_at"] = existing.get("created_at", datetime.now(timezone.utc).isoformat())
        # Increment version and snapshot the old config
        old_version = existing.get("version", 1)
        config["version"] = old_version + 1
        _save_version_snapshot(existing)
    else:
        config.setdefault("uuid", _generate_uuid())
        config.setdefault("version", 1)
        config.setdefault("created_at", datetime.now(timezone.utc).isoformat())

    # Handle greetings: regenerate if trigger fields changed, otherwise preserve
    if _needs_greeting_regen(existing, config):
        if generate_greetings_fn and config.get("model"):
            try:
                config["greetings"] = generate_greetings_fn(
                    config.get("name", "Assistant"),
                    config.get("system_prompt", ""),
                    config.get("model"),
                )
            except Exception as e:
                log.warning("Greeting generation failed: %s", e)
                config.setdefault("greetings", [])
        else:
            config.setdefault("greetings", [])
    else:
        config["greetings"] = existing.get("greetings", [])

    errors = validate_assistant(config)
    if errors:
        raise ValueError("; ".join(errors))

    # Handle rename: if name changed, update ID slug and remove old file
    if existing and existing.get("name") != config.get("name"):
        new_id = _slugify(config.get("name", current_id))
        if new_id != current_id:
            old_path.unlink(missing_ok=True)
            config["id"] = new_id

    path = _assistants_dir() / f"{config['id']}.json"
    with open(path, "w") as f:
        json.dump(config, f, indent=2)

    log.info("Saved assistant: %s (%s) uuid=%s v%d greetings=%d",
             config["id"], config.get("name"), config.get("uuid"),
             config.get("version", 1), len(config.get("greetings", [])))
    return config


def _save_version_snapshot(config: dict) -> None:
    """Save a snapshot of the config before it's overwritten."""
    uid = config.get("uuid")
    version = config.get("version", 1)
    if not uid:
        return
    path = _history_dir() / f"{uid}_v{version}.json"
    try:
        with open(path, "w") as f:
            json.dump(config, f, indent=2)
    except OSError:
        log.warning("Failed to save version snapshot: %s", path)


def list_versions(target_uuid: str) -> list[int]:
    """List all version numbers for an assistant UUID."""
    d = _history_dir()
    versions = []
    prefix = f"{target_uuid}_v"
    for f in d.glob(f"{prefix}*.json"):
        try:
            v = int(f.stem[len(prefix):])
            versions.append(v)
        except ValueError:
            continue
    return sorted(versions)


def get_version(target_uuid: str, version: int) -> dict | None:
    """Load a specific version snapshot."""
    path = _history_dir() / f"{target_uuid}_v{version}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def delete_assistant(assistant_id: str) -> bool:
    if assistant_id == "default":
        raise ValueError("Cannot delete the default assistant")

    path = _assistants_dir() / f"{assistant_id}.json"
    if not path.exists():
        return False
    # Keep version history for archive traceability
    path.unlink()
    log.info("Deleted assistant: %s", assistant_id)
    return True
