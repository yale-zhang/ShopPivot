"""L2 写入计划接口（P05/P06）：建计划 → 审批 → 执行/回查 → 驳回/撤回/补偿。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from bootstrap.container import AppContainer
from bootstrap.deps import assert_shop_scope, get_container, get_current_user, require
from kernel.contexts.approval.application.write_flow import CreateWritePlanCommand
from kernel.contexts.approval.domain.write_plan import WriteExecution, WritePlan
from kernel.contexts.identity.domain.account import Permission
from kernel.contexts.observability.domain.models import AuditEntry
from shared.errors.registry import DomainError

router = APIRouter(prefix="/api/v1", tags=["write"])


class CreatePlanRequest(BaseModel):
    action_code: str = Field(default="S02.price_update", max_length=64)
    platform: str = Field(min_length=1, max_length=32)
    shop_id: str = Field(min_length=1, max_length=64)
    rows: list[dict[str, Any]] = Field(min_length=1, max_length=100)
    idempotency_key: str = Field(min_length=3, max_length=200)
    scene: str = Field(default="S02", pattern=r"^S\d{2}$")


class ApproveRequest(BaseModel):
    reason: str = Field(default="", max_length=255)


class RejectRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=255)


class WithdrawRequest(BaseModel):
    reason: str = Field(default="", max_length=255)


class CompensateRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=255)


def _plan_dict(plan: WritePlan) -> dict[str, Any]:
    return {
        "plan_id": plan.plan_id,
        "action_code": plan.action_code,
        "scene": plan.scene,
        "platform": plan.platform,
        "shop_id": plan.shop_id,
        "status": plan.status.value,
        "summary": plan.summary,
        "impact_scope": plan.impact_scope,
        "rollback_plan": plan.rollback_plan,
        "plan_hash": plan.plan_hash,
        "rows": plan.rows,
        "evidence": plan.evidence,
        "approval_task_id": plan.approval_task_id,
        "execution_id": plan.execution_id,
        "error_code": plan.error_code,
        "error_layer": plan.error_layer,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
        "requested_by": plan.requested_by,
    }


def _execution_dict(execution: WriteExecution) -> dict[str, Any]:
    return {
        "execution_id": execution.execution_id,
        "plan_id": execution.plan_id,
        "task_id": execution.task_id,
        "status": execution.status,
        "applied_rows": execution.applied_rows,
        "before_shot": execution.before_shot,
        "after_shot": execution.after_shot,
        "verify_result": execution.verify_result,
        "details": execution.details,
        "err_code": execution.err_code,
        "err_layer": execution.err_layer,
        "started_at": execution.started_at.isoformat() if execution.started_at else None,
        "ended_at": execution.ended_at.isoformat() if execution.ended_at else None,
    }


def _scoped_plan(container: AppContainer, user, plan_id: str):
    plan = container.write_plans.get(plan_id)
    if plan is None:
        raise DomainError("E008", f"变更计划不存在: {plan_id}", status_override=404)
    assert_shop_scope(user, plan.platform, plan.shop_id)
    return plan


@router.post("/write-plans")
def create_write_plan(
    body: CreatePlanRequest,
    container: AppContainer = Depends(get_container),
    user=Depends(require(Permission.HANDLE_TODO)),
) -> dict[str, Any]:
    assert_shop_scope(user, body.platform, body.shop_id)
    command = CreateWritePlanCommand(
        action_code=body.action_code,
        platform=body.platform,
        shop_id=body.shop_id,
        rows=body.rows,
        requested_by=user.username,
        idempotency_key=body.idempotency_key,
        scene=body.scene,
    )
    plan, task = container.write_flow.create_plan(command)
    container.audit.record(
        AuditEntry(
            actor=user.username,
            action="write_plan.create",
            object_type="write_plan",
            object_id=plan.plan_id,
            after={"action_code": plan.action_code, "rows": len(plan.rows)},
        )
    )
    return {
        "plan": _plan_dict(plan),
        "task_id": task.task_id,
        "sla_expires_at": task.sla_expires_at.isoformat(),
    }


@router.get("/write-plans")
def list_write_plans(
    container: AppContainer = Depends(get_container),
    user=Depends(get_current_user),
) -> dict[str, Any]:
    plans = container.write_plans.recent(50)
    visible = [
        plan
        for plan in plans
        if user.is_owner
        or any(
            scope.platform == plan.platform and scope.shop_id == plan.shop_id
            for scope in user.shops
        )
    ]
    return {
        "items": [_plan_dict(plan) for plan in visible],
        "empty_copy": "暂无变更计划",
        "platform_gate_max": container.settings.platform_gate_max.value,
    }


@router.get("/write-plans/{plan_id}")
def get_write_plan(
    plan_id: str,
    container: AppContainer = Depends(get_container),
    user=Depends(get_current_user),
) -> dict[str, Any]:
    plan = container.write_plans.get(plan_id)
    if plan is None:
        raise DomainError("E008", f"变更计划不存在: {plan_id}", status_override=404)
    executions = container.write_executions.by_plan(plan_id)
    return {
        "plan": _plan_dict(plan),
        "executions": [_execution_dict(item) for item in executions],
    }


@router.post("/write-plans/{plan_id}/approve")
def approve_write_plan(
    plan_id: str,
    body: ApproveRequest,
    container: AppContainer = Depends(get_container),
    user=Depends(require(Permission.APPROVE_L2)),
) -> dict[str, Any]:
    _scoped_plan(container, user, plan_id)
    _scoped_plan(container, user, plan_id)
    _scoped_plan(container, user, plan_id)
    _scoped_plan(container, user, plan_id)
    plan, execution = container.write_flow.approve(
        plan_id, operator=user.username, reason=body.reason
    )
    container.audit.record(
        AuditEntry(
            actor=user.username,
            action="write_plan.approve",
            object_type="write_plan",
            object_id=plan_id,
            reason=body.reason or None,
            after={
                "status": plan.status.value,
                "execution_id": execution.execution_id if execution else None,
                "verified": execution.status if execution else None,
            },
        )
    )
    return {
        "plan": _plan_dict(plan),
        "execution": _execution_dict(execution) if execution else None,
    }


@router.post("/write-plans/{plan_id}/reject")
def reject_write_plan(
    plan_id: str,
    body: RejectRequest,
    container: AppContainer = Depends(get_container),
    user=Depends(require(Permission.APPROVE_L2)),
) -> dict[str, Any]:
    _scoped_plan(container, user, plan_id)
    plan = container.write_flow.reject(plan_id, operator=user.username, reason=body.reason)
    container.audit.record(
        AuditEntry(
            actor=user.username,
            action="write_plan.reject",
            object_type="write_plan",
            object_id=plan_id,
            reason=body.reason,
            after={"status": plan.status.value},
        )
    )
    return {"plan": _plan_dict(plan)}


@router.post("/write-plans/{plan_id}/withdraw")
def withdraw_write_plan(
    plan_id: str,
    body: WithdrawRequest,
    container: AppContainer = Depends(get_container),
    user=Depends(require(Permission.APPROVE_L2)),
) -> dict[str, Any]:
    _scoped_plan(container, user, plan_id)
    plan = container.write_flow.withdraw(plan_id, operator=user.username, reason=body.reason)
    container.audit.record(
        AuditEntry(
            actor=user.username,
            action="write_plan.withdraw",
            object_type="write_plan",
            object_id=plan_id,
            reason=body.reason or None,
            after={"status": plan.status.value},
        )
    )
    return {"plan": _plan_dict(plan)}


@router.post("/write-plans/{plan_id}/compensate")
def compensate_write_plan(
    plan_id: str,
    body: CompensateRequest,
    container: AppContainer = Depends(get_container),
    user=Depends(require(Permission.APPROVE_L2)),
) -> dict[str, Any]:
    _scoped_plan(container, user, plan_id)
    plan = container.write_flow.compensate(plan_id, operator=user.username, reason=body.reason)
    container.audit.record(
        AuditEntry(
            actor=user.username,
            action="write_plan.compensate",
            object_type="write_plan",
            object_id=plan_id,
            reason=body.reason,
            after={"status": plan.status.value},
        )
    )
    return {"plan": _plan_dict(plan)}
