"""执行能力上下文：Worker、能力解析（BC-5）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Protocol

from shared.errors.registry import DomainError


class WorkerKind(str, Enum):
    HEADLESS = "HEADLESS"
    DESKTOP = "DESKTOP"


class WorkerStatus(str, Enum):
    ONLINE = "ONLINE"
    BUSY = "BUSY"
    OFFLINE = "OFFLINE"


@dataclass
class Worker:
    worker_id: str
    kind: WorkerKind
    status: WorkerStatus = WorkerStatus.ONLINE
    capabilities: list[str] = field(default_factory=list)
    queue_depth: int = 0
    last_heartbeat_at: datetime | None = None


class WorkerRepository(Protocol):
    def upsert(self, worker: Worker) -> None: ...

    def get(self, worker_id: str) -> Worker | None: ...

    def list(self) -> list[Worker]: ...


class CapabilityResolver:
    """按场景所需能力判定 HEADLESS / DESKTOP；M0 只有 HEADLESS。"""

    def __init__(self, workers: list[Worker] | None = None, *, desktop_enabled: bool = False) -> None:
        self.workers = workers or []
        self.desktop_enabled = desktop_enabled

    def available(self) -> set[str]:
        result: set[str] = set()
        for worker in self.workers:
            if worker.status is not WorkerStatus.OFFLINE:
                result.update(worker.capabilities)
        return result

    def resolve(self, required: set[str]) -> WorkerKind:
        missing = required - self.available()
        if not missing:
            return WorkerKind.HEADLESS
        if self.desktop_enabled and missing <= {"UIA", "WIN32", "OCR", "COM"}:
            return WorkerKind.DESKTOP
        raise DomainError(
            "E008",
            f"当前无可用执行能力: {', '.join(sorted(missing))}（M0 仅 HEADLESS）",
            details={"missing": sorted(missing)},
        )
