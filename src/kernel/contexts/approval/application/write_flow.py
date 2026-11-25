"""L2 写入闭环用例：建计划 → 审批 → 一次性 token → 执行 → 回查 → 归档/补偿。

安全边界：
- 只有 gate_level=L2 且平台上限 >= L2 才允许建计划；
- token 只由闸门签发，服务端只存 hash，单次消费；
- 执行结果必须回查一致才归档，失败进补偿而不是假装成功。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Mapping
from uuid import uuid4

from kernel.contexts.approval.domain.approval_task import ApprovalStatus, ApprovalTask
from kernel.contexts.approval.domain.gate_policy import GatePolicyService
from kernel.contexts.approval.domain.ports import (
    ApprovalTaskRepository,
    WriteExecutionRepository,
    WritePlanRepository,
    WriteTokenRepository,
)
from kernel.contexts.approval.domain.write_plan import (
    WriteExecution,
    WritePlan,
    WritePlanStatus,
)
from kernel.contexts.integration.application.notification_service import NotificationService
from kernel.contexts.orchestration.domain.ports import Clock
from kernel.contracts.extension_points import (
    ActionResult,
    ActionPlan,
    WriteActionHandler,
    WriteActionRequest,
)
from shared.errors.registry import DomainError
from shared.evidence import EvidenceSet
from shared.gate_level import GateLevel
from shared.run_id import RunId


@dataclass(frozen=True)
class CreateWritePlanCommand:
    action_code: str
    platform: str
    shop_id: str
    rows: list[dict[str, Any]]
    requested_by: str
    idempotency_key: str
    scene: str = "S02"
    params: dict[str, Any] | None = None


class WriteFlowService:
    def __init__(
        self,
        *,
        plans: WritePlanRepository,
        executions: WriteExecutionRepository,
        tokens: WriteTokenRepository,
        approvals: ApprovalTaskRepository,
        handlers: Mapping[str, WriteActionHandler],
        gate: GatePolicyService,
        clock: Clock,
        notifier: NotificationService,
    ) -> None:
        self.plans = plans
        self.executions = executions
        self.tokens = tokens
        self.approvals = approvals
        self.handlers = dict(handlers)
        self.gate = gate
        self.clock = clock
        self.notifier = notifier

    # ------------------------------------------------------------------ create
    def create_plan(self, cmd: CreateWritePlanCommand) -> tuple[WritePlan, ApprovalTask]:
        existing = self.plans.find_by_idempotency(cmd.idempotency_key)
        if existing is not None:
            task = (
                self.approvals.get(existing.approval_task_id)
                if existing.approval_task_id
                else None
            )
            if task is None:
                raise DomainError("E008", "幂等命中的计划缺少审批任务")
            return existing, task

        decision = self.gate.decide(cmd.action_code)
        if not decision.allowed:
            raise DomainError("E007", decision.reason)
        if decision.gate_level is not GateLevel.L2_MANUAL_APPROVAL:
            raise DomainError("E007", f"动作 {cmd.action_code} 不是 L2，不能创建写入计划")
        handler = self.handlers.get(cmd.action_code)
        if handler is None:
            raise DomainError("E008", f"未安装动作处理器: {cmd.action_code}")

        try:
            action: ActionPlan = handler.build(
                WriteActionRequest(
                    platform=cmd.platform,
                    shop_id=cmd.shop_id,
                    rows=cmd.rows,
                    requested_by=cmd.requested_by,
                    params=cmd.params or {},
                )
            )
        except DomainError:
            raise
        except Exception as exc:  # noqa: BLE001 - 动作构建失败要转成可定位错误
            raise DomainError("E006", f"变更清单生成失败: {exc}") from exc

        now = self.clock.now()
        plan = WritePlan.create(
            action_code=cmd.action_code,
            scene=cmd.scene,
            platform=cmd.platform,
            shop_id=cmd.shop_id,
            rows=action.rows,
            before_snapshot=action.before_snapshot,
            summary=action.summary,
            impact_scope=action.impact_scope,
            rollback_plan=action.rollback_plan,
            evidence=action.evidence,
            idempotency_key=cmd.idempotency_key,
            requested_by=cmd.requested_by,
            created_at=now,
        )
        task = ApprovalTask.request(
            run_id=RunId.new(),  # 计划关联键；不与 run_instance 强绑定
            gate_level=GateLevel.L2_MANUAL_APPROVAL,
            action_code=cmd.action_code,
            write_plan={
                "plan_id": plan.plan_id,
                "plan_hash": plan.plan_hash,
                "rows": plan.rows,
                "summary": plan.summary,
                "impact_scope": plan.impact_scope,
                "rollback_plan": plan.rollback_plan,
                "evidence": plan.evidence,
                "before_snapshot": plan.before_snapshot,
                "metric_version": plan.before_snapshot.get("metric_version"),
                "snapshot_time": now.isoformat(),
                "schema_version": "1.0",
                "created_at": now.isoformat(),
            },
            sla_expires_at=now + timedelta(minutes=30),
            idempotency_key=f"plan:{cmd.idempotency_key}",
            scene=cmd.scene,
            platform=cmd.platform,
            shop_id=cmd.shop_id,
            impact_scope=plan.impact_scope,
            requested_by=cmd.requested_by,
        )
        plan.attach_task(task.task_id)
        self.plans.add(plan)
        self.approvals.add(task)
        self.notifier.send(
            event="EVT-05",
            receiver="owner",
            title=f"L2 待确认 · {plan.summary}",
            body=(
                f"{cmd.platform}/{cmd.shop_id} 变更计划 {plan.plan_id} 已冻结，"
                f"影响 {len(plan.rows)} 行，等待审批"
            ),
            dedupe_key=f"EVT-05:{task.task_id}:owner",
            payload={"plan_id": plan.plan_id, "task_id": task.task_id},
        )
        return plan, task

    # ------------------------------------------------------------------ approve / execute
    def approve(
        self,
        plan_id: str,
        *,
        operator: str,
        reason: str = "",
        execute: bool = True,
    ) -> tuple[WritePlan, WriteExecution | None]:
        plan = self._require_plan(plan_id)
        if plan.status is not WritePlanStatus.PENDING_APPROVAL:
            raise DomainError("E007", f"计划当前状态 {plan.status.value}，不能批准")
        task = self._require_task(plan)
        if task.status is not ApprovalStatus.PENDING:
            raise DomainError("E007", f"审批任务当前状态 {task.status.value}，不能批准")

        now = self.clock.now()
        change_order_no = f"CO-{now.strftime('%Y%m%d')}-{uuid4().hex[:4].upper()}"
        before_shot = str(
            plan.before_snapshot.get("shot") or f"shot://before/{plan.plan_id}"
        )
        evidence = EvidenceSet(
            operator=operator,
            decided_at=now,
            change_order_no=change_order_no,
            before_shot=before_shot,
            after_shot="",
        )
        token = task.grant(evidence, now)
        self.tokens.register(
            token=token.token,
            task_id=task.task_id,
            plan_id=plan.plan_id,
            expires_at=token.expires_at,
            issued_by=operator,
        )
        self.approvals.save(task)
        plan.mark_approved()
        self.plans.save(plan)
        if not execute:
            return plan, None
        execution = self._execute(plan, task, token.token)
        return plan, execution

    def _execute(self, plan: WritePlan, task: ApprovalTask, token: str) -> WriteExecution:
        now = self.clock.now()
        if not self.tokens.consume(
            token=token, task_id=task.task_id, plan_id=plan.plan_id, now=now
        ):
            raise DomainError("E007", "WriteToken 无效、已过期或已被使用")
        handler = self._handler(plan.action_code)
        plan.mark_executing()
        task.mark_executing()
        self.plans.save(plan)
        self.approvals.save(task)

        execution = WriteExecution(
            execution_id=WriteExecution.new_id(),
            plan_id=plan.plan_id,
            task_id=task.task_id,
            status="RUNNING",
            before_shot=str(plan.before_snapshot.get("shot") or ""),
            started_at=now,
        )
        try:
            result: ActionResult = handler.apply(plan)
            execution.applied_rows = result.applied_rows
            execution.after_shot = result.after_shot
            execution.details = result.details
            verified = result.verified and handler.verify(plan)
            if not verified:
                raise DomainError("E007", "执行结果回查与预期不一致")
            self.executions.add(execution)
            task.attach_after_shot(result.after_shot)
            task.verify(True)
            task.archive()
            execution.status = "VERIFIED"
            execution.ended_at = self.clock.now()
            execution.verify_result = {"verified": True}
            self.executions.save(execution)
            plan.mark_verified(execution.execution_id)
            self.plans.save(plan)
            self.approvals.save(task)
            return execution
        except DomainError as exc:
            execution.status = "FAILED"
            execution.err_code = exc.code
            execution.err_layer = exc.layer
            execution.verify_result = {"verified": False, "message": exc.message}
            execution.ended_at = self.clock.now()
            if not self.executions.by_plan(plan.plan_id):
                self.executions.add(execution)
            else:
                self.executions.save(execution)
            plan.mark_failed(exc.code, exc.layer or "CODE", execution.execution_id)
            compensated = False
            try:
                if task.status is ApprovalStatus.EXECUTING:
                    task.verify(False)
            except DomainError:
                pass
            # 只有真的写入过才补偿；参数漂移等"未写入"失败不得覆盖外部状态
            if execution.applied_rows:
                try:
                    compensated = handler.compensate(plan)
                except Exception:  # noqa: BLE001 - 补偿失败要保留现场
                    compensated = False
            if compensated:
                plan.compensate()
                try:
                    task.compensate(f"执行失败自动补偿: {exc.message}")
                except DomainError:
                    pass
            self.plans.save(plan)
            self.approvals.save(task)
            self.notifier.send(
                event="EVT-07",
                receiver="ops",
                title=f"写入执行失败 · {plan.summary}",
                body=f"计划 {plan.plan_id} 执行失败：{exc.message}（补偿={compensated}）",
                dedupe_key=f"EVT-07:{plan.plan_id}",
            )
            return execution

    # ------------------------------------------------------------------ other transitions
    def reject(self, plan_id: str, *, operator: str, reason: str) -> WritePlan:
        plan = self._require_plan(plan_id)
        task = self._require_task(plan)
        task.reject(reason, self.clock.now())
        plan.reject()
        self.approvals.save(task)
        self.plans.save(plan)
        self.notifier.send(
            event="EVT-06",
            receiver=plan.requested_by,
            title=f"变更单已驳回 · {plan.summary}",
            body=f"驳回理由：{reason}",
            dedupe_key=f"EVT-06:{task.task_id}:{plan.requested_by}",
        )
        return plan

    def withdraw(self, plan_id: str, *, operator: str, reason: str = "") -> WritePlan:
        plan = self._require_plan(plan_id)
        task = self._require_task(plan)
        task.withdraw()
        plan.withdraw()
        self.approvals.save(task)
        self.plans.save(plan)
        return plan

    def compensate(self, plan_id: str, *, operator: str, reason: str) -> WritePlan:
        plan = self._require_plan(plan_id)
        if plan.status is not WritePlanStatus.VERIFIED:
            raise DomainError("E007", "只有已执行成功的计划可发起补偿")
        handler = self._handler(plan.action_code)
        if not handler.compensate(plan):
            raise DomainError("E007", "补偿未生效，请人工核对平台状态")
        plan.compensate()
        self.plans.save(plan)
        task = self._require_task(plan)
        task.compensate(reason)
        self.approvals.save(task)
        return plan

    # ------------------------------------------------------------------ helpers
    def _require_plan(self, plan_id: str) -> WritePlan:
        plan = self.plans.get(plan_id)
        if plan is None:
            raise DomainError("E008", f"变更计划不存在: {plan_id}", status_override=404)
        return plan

    def _require_task(self, plan: WritePlan) -> ApprovalTask:
        if not plan.approval_task_id:
            raise DomainError("E008", "计划缺少审批任务")
        task = self.approvals.get(plan.approval_task_id)
        if task is None:
            raise DomainError("E008", f"审批任务不存在: {plan.approval_task_id}")
        return task

    def _handler(self, action_code: str) -> WriteActionHandler:
        handler = self.handlers.get(action_code)
        if handler is None:
            raise DomainError("E008", f"未安装动作处理器: {action_code}")
        return handler
