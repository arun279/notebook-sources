from __future__ import annotations

from typing import Any, Callable

from fastapi import BackgroundTasks

from backend.infra.tasks.base import AbstractTaskQueue


class InlineTaskQueue(AbstractTaskQueue):
    """Executes tasks in the same process using FastAPI BackgroundTasks."""

    def __init__(self, bg_tasks: BackgroundTasks | None = None) -> None:
        # This provides ability to supply global BackgroundTasks list.
        self._bg_tasks = bg_tasks

    def enqueue(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:  # noqa: D401
        if self._bg_tasks is None:
            # If not in request context, run synchronously (dev convenience)
            func(*args, **kwargs)
        else:
            self._bg_tasks.add_task(func, *args, **kwargs) 