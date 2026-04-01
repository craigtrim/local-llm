"""Validate every JSON file in the real archives directory."""

import json
from pathlib import Path

import pytest

from local_llm.archive import validate_archive
from local_llm.config import ARCHIVE_DIR

_archive_dir = Path(ARCHIVE_DIR).expanduser()
_archive_files = sorted(_archive_dir.glob("*.json")) if _archive_dir.exists() else []


@pytest.mark.skipif(not _archive_files, reason="No archive files found")
@pytest.mark.parametrize("path", _archive_files, ids=[f.name for f in _archive_files])
def test_archive_file_valid(path: Path):
    data = json.loads(path.read_text())
    errors = validate_archive(data, path.name)
    assert errors == [], f"Validation errors in {path.name}:\n" + "\n".join(errors)
