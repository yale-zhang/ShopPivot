"""L2 写入计划（主文档表 3-23 / 表 3-24 / ADR-08）。

WritePlan 在创建时冻结：动作、目标对象、逐行前值/后值、影响范围、回滚方案、证据引用。
批准后只能按冻结版本执行；任何参数变化都要求重新建计划与审批。
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from shared.errors.registry import DomainError


class WritePlanStatus(str, Enum):
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"
    COMPENSATED = "COMPENSATED"


@dataclass
class WritePlan:
    plan_id: str
    action_code: str
    scene: str
    platform: str
    shop_id: str
    rows: list[dict[str, Any]]
    before_snapshot: dict[str, Any]
    summary: str
    impact_scope: str
    rollback_plan: str
    evidence: list[dict[str, Any]]
    plan_hash: str
    idempotency_key: str
    requested_by: str = "system"
    status: WritePlanStatus = WritePlanStatus.PENDING_APPROVAL
    approval_task_id: str | None = None
    execution_id: str | None = None
    error_code: str | None = None
    error_layer: str | None = None
    created_at: datetime | None = None

    @staticmethod
    def new_id() -> str:
        return f"wp_{uuid4().hex[:16]}"

    @staticmethod
    def hash_plan(
        action_code: str, platform: str, shop_id: str, rows: list[dict[str, Any]]
    ) -> str:
        payload = {
            "action_code": action_code,
            "platform": platform,
            "shop_id": shop_id,
            "rows": rows,
        }
        return hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode()
        ).hexdigest()

    @classmethod
    def create(
        cls,
        *,
        action_code: str,
        scene: str,
        platform: str,
        shop_id: str,
        rows: list[dict[str, Any]],
        before_snapshot: dict[str, Any],
        summary: str,
        impact_scope: str,
        rollback_plan: str,
        evidence: list[dict[str, Any]],
        idempotency_key: str,
        requested_by: str,
        created_at: datetime,
    ) -> "WritePlan":
        if not rows:
            raise DomainError("E006", "WritePlan 不能为空")
        if not rollback_plan.strip():
            raise DomainError("E007", "无回滚方案不得创建 L2 变更单")
        plan = cls(
            plan_id=cls.new_id(),
            action_code=action_code,
            scene=scene,
            platform=platform,
            shop_id=shop_id,
            rows=rows,
            before_snapshot=before_snapshot,
            summary=summary,
            impact_scope=impact_scope,
            rollback_plan=rollback_plan,
            evidence=evidence,
            plan_hash=cls.hash_plan(action_code, platform, shop_id, rows),
            idempotency_key=idempotency_key,
            requested_by=requested_by,
            created_at=created_at,
        )
        return plan

    def attach_task(self, task_id: str) -> None:
        if self.status is not WritePlanStatus.PENDING_APPROVAL:
            raise DomainError("E007", "只有待审批计划可绑定审批任务")
        self.approval_task_id = task_id

    def _ensure(self, expected: WritePlanStatus, action: str) -> None:
        if self.status is not expected:
            raise DomainError(
                "E007",
                f"{action} 需要计划状态 {expected.value}，当前 {self.status.value}",
                details={"plan_id": self.plan_id, "status": self.status.value},
            )

    def mark_approved(self) -> None:
        self._ensure(WritePlanStatus.PENDING_APPROVAL, "批准计划")
        self.status = WritePlanStatus.APPROVED

    def mark_executing(self) -> None:
        self._ensure(WritePlanStatus.APPROVED, "执行计划")
        self.status = WritePlanStatus.EXECUTING

    def mark_verified(self, execution_id: str) -> None:
        if self.status not in {WritePlanStatus.EXECUTING, WritePlanStatus.APPROVED}:
            raise DomainError("E007", "当前状态不能标记成功")
        self.status = WritePlanStatus.VERIFIED
        self.execution_id = execution_id

    def mark_failed(self, code: str, layer: str, execution_id: str | None = None) -> None:
        self.status = WritePlanStatus.FAILED
        self.error_code = code
        self.error_layer = layer
        if execution_id:
            self.execution_id = execution_id

    def reject(self) -> None:
        self._ensure(WritePlanStatus.PENDING_APPROVAL, "驳回计划")
        self.status = WritePlanStatus.REJECTED

    def withdraw(self) -> None:
        self._ensure(WritePlanStatus.APPROVED, "撤回计划")
        self.status = WritePlanStatus.WITHDRAWN

    def compensate(self) -> None:
        if self.status not in {WritePlanStatus.FAILED, WritePlanStatus.VERIFIED}:
            raise DomainError("E007", "只有失败或已执行计划可走补偿")
        self.status = WritePlanStatus.COMPENSATED


@dataclass
class WriteExecution:
    execution_id: str
    plan_id: str
    task_id: str
    status: str = "RUNNING"
    applied_rows: list[dict[str, Any]] = field(default_factory=list)
    before_shot: str = ""
    after_shot: str = ""
    verify_result: dict[str, Any] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)
    err_code: str | None = None
    err_layer: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None

    @staticmethod
    def new_id() -> str:
        return f"we_{uuid4().hex[:16]}"
