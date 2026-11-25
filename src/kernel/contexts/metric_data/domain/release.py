"""口径卡发布自检（ADR-13 B2 / 表 3-26 质量与发布分区）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class ReleaseCheck:
    name: str
    passed: bool
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "passed": self.passed, "detail": self.detail}


@dataclass(frozen=True, slots=True)
class ReleaseResult:
    metric_code: str
    version: str
    passed: bool
    checks: list[ReleaseCheck] = field(default_factory=list)
    checked_at: datetime | None = None
    checked_by: str = "system"

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_code": self.metric_code,
            "version": self.version,
            "gate_passed": self.passed,
            "checks": [check.to_dict() for check in self.checks],
            "checked_at": self.checked_at.isoformat() if self.checked_at else None,
            "checked_by": self.checked_by,
        }


class ProbeRunner(Protocol):
    def run(self, sql_template: str, params: dict[str, Any]) -> Any: ...
