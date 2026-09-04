"""Where the data file lives, and how it is read and written.

The data file is the only irreplaceable thing in the product, so writes are
atomic: a crash leaves the previous file intact rather than truncated JSON.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

from nebula import model
from nebula.model import AppData

APP_DIR = Path.home() / "Library" / "Application Support" / "Nebula"


class DataFileCorrupt(RuntimeError):
    """The data file exists but could not be parsed."""


def data_path(dev: bool = False) -> Path:
    """The data file.

    Absolute, because a bundled app's working directory is `/` — a relative
    path works from a source checkout and silently breaks in the .app.

    Development writes a separate file so that working on the app cannot
    corrupt or wipe real tracked history.
    """
    return APP_DIR / ("data.dev.json" if dev else "data.json")


def load(path: Path, now: datetime) -> AppData:
    """Read the data file, or return the first-launch state if absent."""
    if not path.exists():
        return model.empty_data(now)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return model.from_dict(raw)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        raise DataFileCorrupt(f"Could not read {path}: {error}") from error


def save(data: AppData, path: Path) -> None:
    """Write atomically: serialise to a temp file, then replace.

    `os.replace` is atomic on POSIX, so a reader never sees a half-written
    file and a crash mid-write cannot destroy the previous one. Serialising
    before the replace means a serialisation error leaves the old file alone.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(model.to_dict(data), indent=2)

    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    )
    try:
        with handle as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(handle.name, path)
    except BaseException:
        Path(handle.name).unlink(missing_ok=True)
        raise
