"""运维资产上下文：审计、异常记录、四层定位（BC-6）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from shared.errors.registry import DomainError


@dataclass(frozen=True, slots=True)
class AuditEntry:
    actor: str
    action: str
    object_type: str
    object_id: str
    reason: str | None = None
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    ip: str | None = None
    result: str = "OK"


class AuditPort(Protocol):
    def record(self, entry: AuditEntry) -> None: ...

    def recent(
        self,
        limit: int = 50,
        action: str | None = None,
        actor: str | None = None,
        object_type: str | None = None,
        object_id: str | None = None,
        since: Any = None,
        until: Any = None,
    ) -> list[dict[str, Any]]: ...


class ExceptionPort(Protocol):
    def record(
        self,
        error: DomainError,
        *,
        run_id: str | None = None,
        node_id: str | None = None,
        screenshot_ref: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> int: ...

    def recent(self, limit: int = 50) -> list[dict[str, Any]]: ...


class DeadLetterPort(Protocol):
    def record(
        self,
        error: DomainError,
        *,
        run_id: str,
        node_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> int: ...

    def recent(self, limit: int = 50) -> list[dict[str, Any]]: ...


@dataclass
class FourLayerSnapshot:
    run_id: str
    node_id: str
    err_code: str
    err_layer: str
    evidence: dict[str, Any] = field(default_factory=dict)

    @property
    def locator(self) -> str:
        return f"{self.err_code}/{self.err_layer}"
