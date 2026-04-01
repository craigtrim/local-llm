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
