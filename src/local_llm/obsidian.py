import json
from datetime import datetime, timezone
from pathlib import Path

from .config import OBSIDIAN_TAGS


def _format_callout(role: str, content: str) -> str:
    lines = content.split("\n")
    header = f"> [!{role}]"
    body = "\n".join(f"> {line}" if line else ">" for line in lines)
    return f"{header}\n{body}"


def convert(
    json_path: Path, vault_dir: str, model: str | None = None
) -> Path | None:
    try:
        messages = json.loads(json_path.read_text())
    except Exception:
        return None

    ts = datetime.strptime(json_path.stem, "%Y%m%d_%H%M%S").replace(
        tzinfo=timezone.utc
    )
    iso_date = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
    display_date = ts.strftime("%Y-%m-%d %H:%M")

    # Frontmatter
    fm_lines = ["---", f"date: {iso_date}"]
    if model:
        fm_lines.append(f"model: {model}")
    if OBSIDIAN_TAGS:
        fm_lines.append("tags:")
        for tag in OBSIDIAN_TAGS:
            fm_lines.append(f"  - {tag}")
    fm_lines.append("---")

    # Body
    parts = ["\n".join(fm_lines), "", f"# Chat — {display_date}", ""]
    for msg in messages:
        if msg["role"] == "system":
            continue
        parts.append(_format_callout(msg["role"], msg["content"]))
        parts.append("")

    out_dir = Path(vault_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"Chat {json_path.stem}.md"
    out_path.write_text("\n".join(parts))
    return out_path
