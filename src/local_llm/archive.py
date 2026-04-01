import json
from datetime import datetime, timezone
from pathlib import Path

from .config import ARCHIVE_DIR


def save(messages: list[dict]) -> Path | None:
    if len(messages) <= 1:
        return None

    archive_dir = Path(ARCHIVE_DIR).expanduser()
    archive_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = archive_dir / f"{timestamp}.json"
    with open(path, "w") as f:
        json.dump(messages, f, indent=2)

    return path
