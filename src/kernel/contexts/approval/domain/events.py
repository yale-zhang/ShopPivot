"""审批治理领域事件。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from kernel.contexts.orchestration.domain.events import DomainEvent


@dataclass(frozen=True)
class ApprovalRequested(DomainEvent):
    task_id: str = ""
    run_id: str = ""
    sla_expires_at: str = ""
    proposal_digest: str = ""

    @property
    def payload(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "run_id": self.run_id,
            "sla_expires_at": self.sla_expires_at,
            "proposal_digest": self.proposal_digest,
        }

    @property
    def aggregate_id(self) -> str:
        return self.task_id


@dataclass(frozen=True)
class ApprovalGranted(DomainEvent):
    task_id: str = ""
    change_order_no: str = ""
    operator: str = ""

    @property
    def payload(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "change_order_no": self.change_order_no,
            "operator": self.operator,
        }

    @property
    def aggregate_id(self) -> str:
        return self.task_id


@dataclass(frozen=True)
class ApprovalTransferred(DomainEvent):
    task_id: str = ""
    from_approver: str = ""
    to_approver: str = ""

    @property
    def payload(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "from_approver": self.from_approver,
            "to_approver": self.to_approver,
        }

    @property
    def aggregate_id(self) -> str:
        return self.task_id


@dataclass(frozen=True)
class ApprovalRejected(DomainEvent):
    task_id: str = ""
    reason: str = ""

    @property
    def payload(self) -> dict[str, Any]:
        return {"task_id": self.task_id, "reason": self.reason}

    @property
    def aggregate_id(self) -> str:
        return self.task_id


@dataclass(frozen=True)
class ApprovalExpired(DomainEvent):
    task_id: str = ""
    reason: str = "SLA 超时自动作废"

    @property
    def payload(self) -> dict[str, Any]:
        return {"task_id": self.task_id, "reason": self.reason}

    @property
    def aggregate_id(self) -> str:
        return self.task_id


@dataclass(frozen=True)
class WriteTokenIssued(DomainEvent):
    task_id: str = ""
    ttl_seconds: int = 300

    @property
    def payload(self) -> dict[str, Any]:
        return {"task_id": self.task_id, "ttl_seconds": self.ttl_seconds}

    @property
    def aggregate_id(self) -> str:
        return self.task_id


@dataclass(frozen=True)
class ApprovalEventLog(DomainEvent):
    task_id: str = ""
    status: str = ""
    note: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def payload(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status,
            "note": self.note,
            **self.extra,
        }

    @property
    def aggregate_id(self) -> str:
        return self.task_id
