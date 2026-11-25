"""领域事件（主文档表 8-6）：Outbox 持久化 + 至少一次投递 + 幂等消费。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class DomainEvent:
    event_id: str = field(default_factory=lambda: f"evt_{uuid4().hex[:20]}")
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def event_type(self) -> str:
        return type(self).__name__

    @property
    def payload(self) -> dict[str, Any]:
        return {}

    @property
    def aggregate_id(self) -> str:
        return ""


@dataclass(frozen=True)
class RunStarted(DomainEvent):
    run_id: str = ""
    app_id: str = ""
    config_snapshot_hash: str = ""

    @property
    def payload(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "app_id": self.app_id,
            "config_snapshot_hash": self.config_snapshot_hash,
        }

    @property
    def aggregate_id(self) -> str:
        return self.run_id


@dataclass(frozen=True)
class RunSucceeded(DomainEvent):
    run_id: str = ""
    app_id: str = ""

    @property
    def payload(self) -> dict[str, Any]:
        return {"run_id": self.run_id, "app_id": self.app_id}

    @property
    def aggregate_id(self) -> str:
        return self.run_id


@dataclass(frozen=True)
class RunFailed(DomainEvent):
    run_id: str = ""
    err_code: str = ""
    err_layer: str = ""

    @property
    def payload(self) -> dict[str, Any]:
        return {"run_id": self.run_id, "err_code": self.err_code, "err_layer": self.err_layer}

    @property
    def aggregate_id(self) -> str:
        return self.run_id


@dataclass(frozen=True)
class ReportGenerated(DomainEvent):
    report_id: str = ""
    run_id: str = ""
    metric_version: str = ""

    @property
    def payload(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "run_id": self.run_id,
            "metric_version": self.metric_version,
        }

    @property
    def aggregate_id(self) -> str:
        return self.report_id
