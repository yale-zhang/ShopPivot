"""ApprovalTask 聚合（主文档表 3-9 / 表 8-4 / 代码清单 8-3）。

不变量：
- 只有 PENDING 可批准；
- 超 SLA → 自动作废，绝不默认执行；
- 四要素留痕完整才允许批准与归档；
- 驳回不自动重试；
- 一次批准只签发一枚绑定 task_id 的短时效 token。
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any
from uuid import uuid4

from kernel.contexts.approval.domain.events import (
    ApprovalExpired,
    ApprovalGranted,
    ApprovalRejected,
    ApprovalRequested,
    ApprovalTransferred,
    WriteTokenIssued,
)
from kernel.contexts.approval.domain.write_token import WriteToken
from kernel.contexts.orchestration.domain.events import DomainEvent
from shared.errors.registry import DomainError
from shared.evidence import EvidenceSet
from shared.gate_level import GateLevel
from shared.run_id import RunId


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    EXECUTING = "EXECUTING"
    VERIFIED = "VERIFIED"
    VERIFY_FAILED = "VERIFY_FAILED"
    ARCHIVED = "ARCHIVED"
    WITHDRAWN = "WITHDRAWN"
    COMPENSATED = "COMPENSATED"


@dataclass
class ApprovalTask:
    task_id: str
    run_id: RunId
    gate_level: GateLevel
    action_code: str
    write_plan: dict[str, Any]
    write_plan_hash: str
    sla_expires_at: datetime
    idempotency_key: str
    scene: str = ""
    platform: str = ""
    shop_id: str = ""
    impact_scope: str | None = None
    status: ApprovalStatus = ApprovalStatus.PENDING
    evidence: EvidenceSet | None = None
    change_order_no: str | None = None
    requested_by: str = "system"
    approver: str = "owner"
    reason: str | None = None
    _events: list[DomainEvent] = field(default_factory=list, repr=False)

    @staticmethod
    def new_task_id() -> str:
        return f"task_{uuid4().hex[:16]}"

    @staticmethod
    def hash_plan(plan: dict[str, Any]) -> str:
        return hashlib.sha256(
            json.dumps(plan, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()

    @classmethod
    def request(
        cls,
        *,
        run_id: RunId,
        gate_level: GateLevel,
        action_code: str,
        write_plan: dict[str, Any],
        sla_expires_at: datetime,
        idempotency_key: str,
        scene: str = "",
        platform: str = "",
        shop_id: str = "",
        impact_scope: str | None = None,
        requested_by: str = "system",
        approver: str = "owner",
    ) -> "ApprovalTask":
        if gate_level is not GateLevel.L2_MANUAL_APPROVAL:
            raise DomainError("E007", "只有 L2 动作才创建审批任务")
        if not idempotency_key:
            raise DomainError("E007", "审批任务必须带幂等键")
        task = cls(
            task_id=cls.new_task_id(),
            run_id=run_id,
            gate_level=gate_level,
            action_code=action_code,
            write_plan=write_plan,
            write_plan_hash=cls.hash_plan(write_plan),
            sla_expires_at=sla_expires_at,
            idempotency_key=idempotency_key,
            scene=scene,
            platform=platform,
            shop_id=shop_id,
            impact_scope=impact_scope,
            requested_by=requested_by,
            approver=approver,
        )
        task._events.append(
            ApprovalRequested(
                task_id=task.task_id,
                run_id=run_id.value,
                sla_expires_at=sla_expires_at.isoformat(),
                proposal_digest=task.write_plan_hash,
            )
        )
        return task

    def _ensure_pending(self, action: str) -> None:
        if self.status is not ApprovalStatus.PENDING:
            raise DomainError(
                "E007",
                f"{action} 需要 PENDING 状态，当前 {self.status.value}",
                details={"task_id": self.task_id, "status": self.status.value},
            )

    def grant(self, evidence: EvidenceSet, now: datetime, ttl_seconds: int = 300) -> WriteToken:
        self._ensure_pending("批准")
        if now > self.sla_expires_at:
            self.status = ApprovalStatus.EXPIRED
            self._events.append(ApprovalExpired(task_id=self.task_id))
            raise DomainError("E007", "SLA 已超时，任务自动作废（不默认执行）")
        missing = evidence.approval_missing_fields()
        if missing:
            raise DomainError(
                "E007",
                f"批准所需证据不完整: {', '.join(missing)}",
                details={"missing": missing},
            )
        self.status = ApprovalStatus.APPROVED
        self.evidence = evidence
        self.change_order_no = evidence.change_order_no
        self._events.append(
            ApprovalGranted(
                task_id=self.task_id,
                change_order_no=evidence.change_order_no,
                operator=evidence.operator,
            )
        )
        token = WriteToken.issue(self.task_id, now, ttl_seconds)
        self._events.append(
            WriteTokenIssued(task_id=self.task_id, ttl_seconds=token.ttl_seconds)
        )
        return token

    def attach_after_shot(self, after_shot: str) -> None:
        if self.evidence is None:
            raise DomainError("E007", "尚未批准，不能补执行后截图")
        if not after_shot:
            raise DomainError("E007", "执行后截图不能为空")
        from dataclasses import replace as _replace

        self.evidence = _replace(self.evidence, after_shot=after_shot)

    def transfer_to(self, approver: str, now: datetime, sla_minutes: int = 30) -> None:
        if self.status is not ApprovalStatus.PENDING:
            raise DomainError("E007", "只有待确认任务可转交")
        if not approver.strip():
            raise DomainError("E007", "转交必须指定审批人")
        if approver == self.approver:
            raise DomainError("E007", "转交对象不能是当前审批人")
        previous = self.approver
        self.approver = approver
        self.sla_expires_at = now + timedelta(minutes=sla_minutes)
        self._events.append(
            ApprovalTransferred(
                task_id=self.task_id, from_approver=previous, to_approver=approver
            )
        )

    def withdraw(self) -> None:
        if self.status is not ApprovalStatus.APPROVED:
            raise DomainError("E007", "只有已批准且未执行的任务可撤回")
        self.status = ApprovalStatus.WITHDRAWN

    def reject(self, reason: str, now: datetime) -> None:
        self._ensure_pending("驳回")
        if not reason.strip():
            raise DomainError("E007", "驳回必须填写理由")
        self.status = ApprovalStatus.REJECTED
        self.reason = reason
        self._events.append(ApprovalRejected(task_id=self.task_id, reason=reason))

    def expire(self, now: datetime) -> bool:
        if self.status is not ApprovalStatus.PENDING:
            return False
        if now < self.sla_expires_at:
            return False
        self.status = ApprovalStatus.EXPIRED
        self._events.append(ApprovalExpired(task_id=self.task_id))
        return True

    def mark_executing(self) -> None:
        if self.status is not ApprovalStatus.APPROVED:
            raise DomainError("E007", "只有已批准任务可进入执行")
        self.status = ApprovalStatus.EXECUTING

    def verify(self, consistent: bool, note: str = "") -> None:
        if self.status is not ApprovalStatus.EXECUTING:
            raise DomainError("E007", "只有执行中任务可做结果校验")
        if consistent:
            self.status = ApprovalStatus.VERIFIED
            return
        self.status = ApprovalStatus.VERIFY_FAILED
        raise DomainError(
            "E007",
            "执行后回查与预期不一致，已停止后续并进入回滚评估",
            details={"task_id": self.task_id, "note": note},
        )

    def archive(self) -> None:
        if self.status is not ApprovalStatus.VERIFIED or self.evidence is None:
            raise DomainError("E007", "未校验或未留痕不得归档")
        if self.evidence.missing_fields():
            raise DomainError("E007", "四要素留痕不完整，不得归档")
        self.status = ApprovalStatus.ARCHIVED

    def compensate(self, reason: str) -> None:
        if self.status not in {
            ApprovalStatus.EXECUTING,
            ApprovalStatus.VERIFY_FAILED,
            ApprovalStatus.ARCHIVED,
        }:
            raise DomainError("E007", "只有执行中/校验失败/已归档任务可走补偿")
        self.status = ApprovalStatus.COMPENSATED
        self.reason = reason

    def pull_events(self) -> list[DomainEvent]:
        events, self._events = self._events, []
        return events
