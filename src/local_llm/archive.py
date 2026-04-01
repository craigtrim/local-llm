import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .config import ARCHIVE_DIR


def _slugify(text: str, max_len: int = 60) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_len].rstrip("-")


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
    return data.get("messages", [])
