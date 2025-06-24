from __future__ import annotations

import abc
from typing import Any, Callable


class AbstractTaskQueue(abc.ABC):
    """Abstraction of a background task runner."""

    @abc.abstractmethod
    def enqueue(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:  # noqa: D401
        """Schedule ``func`` to run in the background."""
        ... 