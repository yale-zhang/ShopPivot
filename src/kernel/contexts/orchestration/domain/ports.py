"""编排上下文端口（领域层只声明契约）。"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from kernel.contexts.orchestration.domain.events import DomainEvent
from kernel.contexts.orchestration.domain.run import Run
from shared.run_id import RunId


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class RunRepository(Protocol):
    def add(self, run: Run) -> None: ...

    def save(self, run: Run) -> None: ...

    def get(self, run_id: RunId) -> Run | None: ...

    def recent(self, limit: int = 20) -> list[Run]: ...


class IdempotencyStore(Protocol):
    def get(self, key: str) -> str | None: ...

    def claim(self, key: str, run_id: str) -> str | None:
        """返回 None 表示抢占成功；返回已存在 run_id 表示重复。"""
        ...


class EventPublisher(Protocol):
    def publish_all(self, events: list[DomainEvent]) -> None: ...
