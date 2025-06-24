from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

from backend.infra.storage.base import AbstractStorage
from backend.settings import settings


class LocalFileStorage(AbstractStorage):
    """Stores artefacts under the configured data directory on the local FS."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or settings.data_dir
        self.root.mkdir(parents=True, exist_ok=True)

    def _abs(self, relative: Path) -> Path:
        return self.root / relative

    def save_bytes(self, relative_path: Path, data: bytes) -> Path:  # noqa: D401
        abs_path = self._abs(relative_path)
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_bytes(data)
        return abs_path

    def open(self, relative_path: Path, mode: str = "rb") -> BinaryIO:  # noqa: D401
        return self._abs(relative_path).open(mode)

    def exists(self, relative_path: Path) -> bool:
        return self._abs(relative_path).exists() 