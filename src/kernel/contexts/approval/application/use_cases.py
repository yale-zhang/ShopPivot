"""审批用例：发起 / 批准 / 驳回 / 超时作废。

平台上限在用例层再校验一次：M0 上限 L0 时，即使有人构造了 L2 任务，
批准也会被拒绝（不签发 WriteToken、不触达 /write）。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from kernel.contexts.approval.domain.approval_task import ApprovalTask
from kernel.contexts.approval.domain.gate_policy import GatePolicyService
from kernel.contexts.approval.domain.ports import ApprovalTaskRepository
from shared.errors.registry import DomainError
from shared.evidence import EvidenceSet
from shared.gate_level import GateLevel
from shared.run_id import RunId


@dataclass(frozen=True)
class RequestApprovalCommand:
    run_id: RunId
    action_code: str
    write_plan: dict[str, Any]
    idempotency_key: str
    scene: str = ""
    platform: str = ""
    shop_id: str = ""
    impact_scope: str | None = None
    requested_by: str = "system"
    sla_seconds: int = 30 * 60


class RequestApprovalUseCase:
    def __init__(
        self,
        repo: ApprovalTaskRepository,
        policy: GatePolicyService,
        *,
        clock: Any,
    ) -> None:
        self.repo = repo
        self.policy = policy
        self.clock = clock

    def __call__(self, cmd: RequestApprovalCommand) -> ApprovalTask:
        existing = self.repo.find_by_idempotency(cmd.idempotency_key)
        if existing is not None:
            return existing
        decision = self.policy.decide(cmd.action_code)
        if not decision.allowed:
            raise DomainError("E007", decision.reason, details={"action_code": cmd.action_code})
        if decision.gate_level is not GateLevel.L2_MANUAL_APPROVAL:
            raise DomainError("E007", f"动作 {cmd.action_code} 不是 L2，无需审批")
        now = self.clock.now()
        task = ApprovalTask.request(
            run_id=cmd.run_id,
            gate_level=GateLevel.L2_MANUAL_APPROVAL,
            action_code=cmd.action_code,
            write_plan=cmd.write_plan,
            sla_expires_at=now + timedelta(seconds=cmd.sla_seconds),
            idempotency_key=cmd.idempotency_key,
            scene=cmd.scene,
            platform=cmd.platform,
            shop_id=cmd.shop_id,
            impact_scope=cmd.impact_scope,
            requested_by=cmd.requested_by,
        )
        self.repo.add(task)
        return task


@dataclass(frozen=True)
class GrantApprovalCommand:
    task_id: str
    evidence: EvidenceSet
    actor_role: str = "OWNER"


class GrantApprovalUseCase:
    def __init__(
        self,
        repo: ApprovalTaskRepository,
        *,
        platform_ceiling: GateLevel = GateLevel.L0_READ_ONLY,
        clock: Any,
    ) -> None:
        self.repo = repo
        self.platform_ceiling = platform_ceiling
        self.clock = clock

    def __call__(self, cmd: GrantApprovalCommand) -> ApprovalTask:
        if self.platform_ceiling.rank < GateLevel.L2_MANUAL_APPROVAL.rank:
            raise DomainError(
                "E007",
                f"平台当前上限 {self.platform_ceiling.value}，写入未启用，禁止批准",
            )
        task = self.repo.get(cmd.task_id)
        if task is None:
            raise DomainError("E007", f"审批任务不存在: {cmd.task_id}")
        task.grant(cmd.evidence, self.clock.now())
        self.repo.save(task)
        return task


class RejectApprovalUseCase:
    def __init__(self, repo: ApprovalTaskRepository, *, clock: Any) -> None:
        self.repo = repo
        self.clock = clock

    def __call__(self, task_id: str, reason: str) -> ApprovalTask:
        task = self.repo.get(task_id)
        if task is None:
            raise DomainError("E007", f"审批任务不存在: {task_id}")
        task.reject(reason, self.clock.now())
        self.repo.save(task)
        return task


class ExpireApprovalsUseCase:
    def __init__(self, repo: ApprovalTaskRepository, *, clock: Any) -> None:
        self.repo = repo
        self.clock = clock

    def __call__(self) -> list[str]:
        expired: list[str] = []
        now = self.clock.now()
        for task in self.repo.overdue(now):
            if task.expire(now):
                self.repo.save(task)
                expired.append(task.task_id)
        return expired


def describe_status(now: datetime, sla: datetime) -> str:
    if now > sla:
        return "EXPIRED"
    remaining = int((sla - now).total_seconds())
    return f"{remaining // 60}m{remaining % 60:02d}s"
