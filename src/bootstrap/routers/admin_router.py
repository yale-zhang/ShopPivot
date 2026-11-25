"""P10 口径卡与发布自检 / P12 权限与订阅 / 通知模板（M1）。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from bootstrap.container import AppContainer
from bootstrap.deps import get_container, get_current_user, require, require_owner
from kernel.contexts.identity.domain.account import ROLE_PERMISSIONS, Permission, Role
from kernel.contexts.metric_data.application.release_gate import MetricReleaseService
from kernel.contexts.observability.domain.models import AuditEntry
from shared.errors.registry import DomainError

router = APIRouter(prefix="/api/v1", tags=["admin"])


def _latest_s01_view(container: AppContainer):
    run = next(
        (
            item
            for item in container.runs.recent(50)
            if item.scene == "S01" and item.status.value == "SUCCEEDED"
        ),
        None,
    )
    if run is None:
        return None, None
    report = next(
        (item for item in container.reports.recent(50) if item.run_id == run.run_id), None
    )
    if report is None:
        return run, None
    view = container.report_builder.build(run, report.channel)
    view.metric_version = report.metric_version
    return run, view


@router.get("/metric-cards")
def list_metric_cards(
    container: AppContainer = Depends(get_container),
    user=Depends(get_current_user),
) -> dict:
    platform = container.settings.platform_source or container.settings.platform
    latest: dict[str, Any] = {}
    for definition in container.metrics.definitions(platform):
        current = latest.get(definition.metric_code)
        if current is None or definition.version > current.version:
            latest[definition.metric_code] = definition
    items = []
    for code in sorted(latest):
        definition = latest[code]
        release = container.releases.latest(code, definition.version)
        items.append(
            {
                "metric_code": definition.metric_code,
                "display_name": definition.display_name,
                "version": definition.version,
                "unit": definition.unit,
                "additivity": definition.additivity.value,
                "null_policy": definition.null_policy.name,
                "source_mapping": definition.source_mapping,
                "release": release,
            }
        )
    return {"items": items, "empty_copy": "尚无已发布口径卡"}


@router.get("/metric-cards/{metric_code}/diff")
def metric_diff(
    metric_code: str,
    from_version: str | None = Query(default=None, alias="from"),
    to_version: str | None = Query(default=None, alias="to"),
    container: AppContainer = Depends(get_container),
    user=Depends(get_current_user),
) -> dict:
    target = container.metrics.definition(metric_code)
    if target is None:
        raise DomainError("E008", f"口径卡不存在: {metric_code}", status_override=404)
    left = container.metrics.definition(metric_code, from_version) if from_version else None
    right = (
        container.metrics.definition(metric_code, to_version) if to_version else target
    )
    if right is None:
        raise DomainError("E008", f"目标版本不存在: {to_version}", status_override=404)
    if left is None:
        return {
            "metric_code": metric_code,
            "from": None,
            "to": right.version,
            "diffs": [],
            "note": "没有可比较的历史版本；当前为该指标首个版本",
        }
    fields = [
        "display_name",
        "unit",
        "precision",
        "additivity",
        "formula",
        "denominator",
        "null_policy",
        "source_mapping",
    ]
    diffs = []
    for field in fields:
        before = getattr(left, field)
        after = getattr(right, field)
        before_value = before.value if hasattr(before, "value") else before
        after_value = after.value if hasattr(after, "value") else after
        if str(before_value) != str(after_value):
            diffs.append({"field": field, "before": before_value, "after": after_value})
    return {
        "metric_code": metric_code,
        "from": left.version,
        "to": right.version,
        "diffs": diffs,
        "note": "口径变更新旧版本不直接连线；发布需通过发布自检" if diffs else "无字段差异",
    }


@router.post("/metric-cards/{metric_code}/release")
def release_metric_card(
    metric_code: str,
    container: AppContainer = Depends(get_container),
    user=Depends(require_owner),
) -> dict:
    definition = container.metrics.definition(metric_code)
    if definition is None:
        raise DomainError("E008", f"口径卡不存在: {metric_code}", status_override=404)
    card = next(
        (
            item
            for item in container.metrics.cards()
            if item["metric_code"] == metric_code and item["version"] == definition.version
        ),
        None,
    )
    run, view = _latest_s01_view(container)
    sample_values: dict[str, Any] = {}
    if run is not None:
        sample_values = {
            row["metric_code"]: row["value"] for row in container.dws.by_run(run.run_id)
        }
    service: MetricReleaseService = container.release_gate
    result = service.run(
        definition,
        card_payload=card["card"] if card else None,
        view=view,
        run_id=run.run_id.value if run else None,
        checked_by=user.username,
        sample_values=sample_values,
    )
    container.releases.add(result)
    container.audit.record(
        AuditEntry(
            actor=user.username,
            action="metric.release_check",
            object_type="metric_card",
            object_id=f"metric.{metric_code}@{definition.version}",
            result="OK" if result.passed else "FAIL",
            after={"checks": [check.to_dict() for check in result.checks]},
        )
    )
    if not result.passed:
        raise DomainError(
            "E007",
            "发布自检未通过，口径卡未发布",
            details={"release": result.to_dict()},
        )
    return result.to_dict()


@router.get("/metric-cards/{metric_code}/release")
def latest_release(
    metric_code: str,
    container: AppContainer = Depends(get_container),
    user=Depends(get_current_user),
) -> dict:
    definition = container.metrics.definition(metric_code)
    if definition is None:
        raise DomainError("E008", f"口径卡不存在: {metric_code}", status_override=404)
    release = container.releases.latest(metric_code, definition.version)
    if release is None:
        return {
            "metric_code": metric_code,
            "version": definition.version,
            "gate_passed": False,
            "checks": [],
            "checked_at": None,
            "note": "尚未执行发布自检",
        }
    return release


class SubscriptionRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    event: str = Field(pattern=r"^EVT-\d{2}$")
    receiver: str = Field(min_length=1, max_length=64)
    channel: str = Field(default="CONSOLE", max_length=24)
    window: str = Field(default="昨日", max_length=32)
    thresholds: dict[str, float] = Field(default_factory=dict)
    silent_window: str | None = Field(default=None, max_length=64)


@router.get("/subscriptions")
def list_subscriptions(
    container: AppContainer = Depends(get_container),
    user=Depends(get_current_user),
) -> dict:
    return {
        "items": [item.to_dict() for item in container.subscriptions.all()],
        "empty_copy": "暂无订阅",
        "channels": ["CONSOLE", "DINGTALK", "WECOM", "EMAIL"],
    }


@router.post("/subscriptions")
def create_subscription(
    body: SubscriptionRequest,
    container: AppContainer = Depends(get_container),
    user=Depends(require(Permission.MANAGE_SUBSCRIPTIONS)),
) -> dict:
    subscription_id = container.subscriptions.add(
        name=body.name,
        event=body.event,
        receiver=body.receiver,
        channel=body.channel,
        window=body.window,
        thresholds=body.thresholds,
        silent_window=body.silent_window,
    )
    container.audit.record(
        AuditEntry(
            actor=user.username,
            action="subscription.create",
            object_type="subscription",
            object_id=str(subscription_id),
            after=body.model_dump(),
        )
    )
    return {"id": subscription_id, "status": "CREATED"}


@router.delete("/subscriptions/{subscription_id}")
def delete_subscription(
    subscription_id: int,
    container: AppContainer = Depends(get_container),
    user=Depends(require(Permission.MANAGE_SUBSCRIPTIONS)),
) -> dict:
    if not container.subscriptions.delete(subscription_id):
        raise DomainError("E008", f"订阅不存在: {subscription_id}", status_override=404)
    container.audit.record(
        AuditEntry(
            actor=user.username,
            action="subscription.delete",
            object_type="subscription",
            object_id=str(subscription_id),
        )
    )
    return {"id": subscription_id, "status": "DELETED"}


@router.get("/notifications/templates")
def notification_templates(
    container: AppContainer = Depends(get_container),
    user=Depends(get_current_user),
) -> dict:
    items = [
        {
            "id": contribution.id,
            "module": contribution.module,
            **contribution.config,
        }
        for contribution in container.registry.by_kind("NotificationTemplate")
    ]
    return {"items": items}


@router.get("/identity/roles")
def role_matrix(
    container: AppContainer = Depends(get_container),
    user=Depends(get_current_user),
) -> dict:
    roles = []
    for role in Role:
        roles.append(
            {
                "role": role.value,
                "permissions": sorted(permission.value for permission in ROLE_PERMISSIONS[role]),
            }
        )
    return {
        "roles": roles,
        "shops": [
            {"platform": scope.platform, "shop_id": scope.shop_id, "role": user.role.value}
            for scope in user.shops
        ],
        "note": "M1 仍为 3 角色 + shop_scope；画布只读 token 由 /n8n/command 单独约束",
    }
