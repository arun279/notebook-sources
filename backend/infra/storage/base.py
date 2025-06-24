from __future__ import annotations

import abc
from pathlib import Path
from typing import BinaryIO


class AbstractStorage(abc.ABC):
    """Abstract file storage to support local filesystem or cloud buckets."""

    @abc.abstractmethod
    def save_bytes(self, relative_path: Path, data: bytes) -> Path:
        ...

    @abc.abstractmethod
    def open(self, relative_path: Path, mode: str = "rb") -> BinaryIO:
        ...

    @abc.abstractmethod
    def exists(self, relative_path: Path) -> bool:  # noqa: D401
        ... 