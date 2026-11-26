"""运营工作台读接口：上下文 / 导航 / 卡片 / 日报 / 下钻 / 待办 / 变更单 / 模块 / 审计。"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from bootstrap.container import AppContainer
from bootstrap.deps import (
    SessionUser,
    assert_shop_scope,
    get_container,
    get_current_user,
    require,
    require_owner,
)
from kernel.contexts.identity.domain.account import Permission
from kernel.contexts.integration.domain.desensitizer import Desensitizer
from kernel.contexts.metric_data.domain.report import DailyReportView
from kernel.contexts.observability.domain.models import AuditEntry
from kernel.persistence.tables import ModuleStateRow
from shared.errors.registry import DomainError

router = APIRouter(prefix="/api/v1", tags=["workbench"])


class TransferRequest(BaseModel):
    approver: str = Field(min_length=1, max_length=64)
    reason: str = Field(default="", max_length=255)


PAGES: list[dict[str, Any]] = [
    {"page_id": "P01", "menu": "① 日常运营", "title": "经营看板", "roles": ["OWNER", "EDITOR", "VIEWER"]},
    {"page_id": "P02", "menu": "① 日常运营", "title": "评价与口碑", "roles": ["OWNER", "EDITOR", "VIEWER"]},
    {"page_id": "P03", "menu": "① 日常运营", "title": "库存与补货", "roles": ["OWNER", "EDITOR", "VIEWER"]},
    {"page_id": "P04", "menu": "① 日常运营", "title": "活动与投放", "roles": ["OWNER", "EDITOR"]},
    {"page_id": "P05", "menu": "② 审批与待办", "title": "我的待办", "roles": ["OWNER", "EDITOR", "VIEWER"]},
    {"page_id": "P06", "menu": "② 审批与待办", "title": "变更单详情", "roles": ["OWNER", "EDITOR", "VIEWER"]},
    {"page_id": "P07", "menu": "② 审批与待办", "title": "审批记录与审计", "roles": ["OWNER"]},
    {"page_id": "P08", "menu": "② 审批与待办", "title": "对账与差异", "roles": ["OWNER", "EDITOR"]},
    {"page_id": "P09", "menu": "③ 治理与配置", "title": "场景与模块", "roles": ["OWNER"]},
    {"page_id": "P10", "menu": "③ 治理与配置", "title": "口径与数据合同", "roles": ["OWNER"]},
    {"page_id": "P11", "menu": "③ 治理与配置", "title": "机器人与日志", "roles": ["OWNER"]},
    {"page_id": "P12", "menu": "③ 治理与配置", "title": "权限与订阅", "roles": ["OWNER"]},
    {"page_id": "P13", "menu": "① 日常运营", "title": "选品与采购", "roles": ["OWNER", "EDITOR"]},
    {"page_id": "P14", "menu": "③ 治理与配置", "title": "技能中心", "roles": ["OWNER"]},
]

KERNEL_CARDS: dict[str, list[dict[str, Any]]] = {
    "P05": [
        {
            "card_id": "card.pending_approval",
            "page_id": "P05",
            "module": "kernel",
            "title": "L2 待确认",
            "slot": "main",
            "data_endpoint": "/api/v1/todos",
            "empty_state_copy": "暂无待办",
            "order": 10,
        }
    ],
    "P09": [
        {
            "card_id": "card.module_list",
            "page_id": "P09",
            "module": "kernel",
            "title": "模块列表",
            "slot": "main",
            "data_endpoint": "/api/v1/modules",
            "empty_state_copy": "仅基础模块已启用",
            "order": 10,
        }
    ],
    "P07": [
        {
            "card_id": "card.audit",
            "page_id": "P07",
            "module": "kernel",
            "title": "审批记录与审计",
            "slot": "main",
            "data_endpoint": "/api/v1/approvals/history",
            "empty_state_copy": "该时间窗无审批记录",
            "order": 10,
        }
    ],
    "P10": [
        {
            "card_id": "card.metric_card_list",
            "page_id": "P10",
            "module": "kernel",
            "title": "口径卡与发布自检",
            "slot": "main",
            "data_endpoint": "/api/v1/metric-cards",
            "empty_state_copy": "尚无已发布口径卡",
            "order": 10,
        }
    ],
    "P11": [
        {
            "card_id": "card.robot_health",
            "page_id": "P11",
            "module": "kernel",
            "title": "机器人与日志",
            "slot": "main",
            "data_endpoint": "/api/v1/workers",
            "empty_state_copy": "暂无在线机器人",
            "order": 10,
        }
    ],
    "P12": [
        {
            "card_id": "card.subscriptions",
            "page_id": "P12",
            "module": "kernel",
            "title": "权限与订阅",
            "slot": "main",
            "data_endpoint": "/api/v1/subscriptions",
            "empty_state_copy": "暂无订阅",
            "order": 10,
        }
    ],
}


def _now() -> datetime:
    return datetime.now(UTC)


def _latest_report(container: AppContainer, platform: str, shop_id: str):
    for report in container.reports.recent(50):
        if report.platform == platform and report.shop_id == shop_id:
            return report
    return None


def _alerts(view: DailyReportView, thresholds: dict[str, float]) -> list[dict[str, Any]]:
    if not view.rows:
        return []
    latest = view.rows[-1]
    alerts: list[dict[str, Any]] = []
    rules = [
        ("cvr", "cvr_min", "转化率低于阈值"),
        ("roi", "roi_min", "投产比低于阈值"),
        ("dsr", "dsr_min", "DSR 低于阈值"),
    ]
    for metric_code, key, label in rules:
        limit = thresholds.get(key)
        cell = latest.cells.get(metric_code)
        if limit is None or cell is None or cell.raw is None:
            continue
        if float(cell.raw) < float(limit):
            alerts.append(
                {
                    "metric_code": metric_code,
                    "threshold": limit,
                    "value": cell.value,
                    "message": f"{label}（{cell.value} < {limit}）",
                }
            )
    return alerts


def _report_payload(
    container: AppContainer, report_id: str, user: SessionUser
) -> dict[str, Any]:
    report = container.reports.get(report_id)
    if report is None:
        raise DomainError("E008", f"报表不存在: {report_id}", status_override=404)
    run = container.runs.get(report.run_id)
    if run is None:
        raise DomainError("E008", f"报表关联的运行不存在: {report.run_id.value}", status_override=404)
    view = container.report_builder.build(run, report.channel)
    view.metric_version = report.metric_version
    scene_config = container.scene_configs.get(run.scene, {})
    thresholds = dict(scene_config.get("thresholds", {}))
    columns = [
        {
            "key": column.key,
            "label": column.label,
            "unit": column.unit,
            "precision": column.precision,
            "additivity": column.additivity.value,
            "additivity_label": column.additivity_label,
            "metric_version": column.metric_version,
            "display_order": column.display_order,
            "source": column.source,
            "drill": column.drill,
            "null_policy": column.null_policy.value,
        }
        for column in sorted(view.columns, key=lambda c: (c.display_order, c.key))
    ]
    rows = [
        {
            "stat_date": row.stat_date.isoformat(),
            "cells": {
                key: {
                    "value": cell.value,
                    "raw": cell.raw,
                    "null_reason": cell.null_reason,
                    "metric_code": cell.metric_code,
                }
                for key, cell in row.cells.items()
            },
        }
        for row in view.rows
    ]
    return {
        "report_id": report.report_id,
        "run_id": report.run_id.value,
        "platform": report.platform,
        "shop_id": report.shop_id,
        "window": {"start": report.window.start.isoformat(), "end": report.window.end.isoformat()},
        "window_label": report.window.label,
        "metric_version": report.metric_version,
        "watermark": report.watermark,
        "channel": report.channel.value,
        "channel_label": report.channel.label,
        "generated_at": report.generated_at.isoformat(),
        "data_state": view.data_state,
        "empty_copy": view.empty_copy,
        "columns": columns,
        "rows": rows,
        "alerts": _alerts(view, thresholds),
        "readonly": container.settings.readonly_mode,
        "drill": "指标 → 口径卡 → run_id → ODS 原始证据",
        "config_snapshot_hash": run.config_snapshot.hash,
        "gate_level_max": run.gate_level_max.value,
    }


@router.get("/workbench/contexts")
def contexts(
    container: AppContainer = Depends(get_container),
    user: SessionUser = Depends(get_current_user),
) -> dict[str, Any]:
    allowed = {
        platform
        for platform in container.adapters
        if user.is_owner
        or any(
            scope.platform == platform and scope.shop_id == container.settings.shop_id
            for scope in user.shops
        )
    }
    platforms = sorted(allowed)
    metric_versions = sorted(
        {d.version for d in container.metrics.definitions(
            container.settings.platform_source or container.settings.platform
        )}
    )
    return {
        "platforms": platforms,
        "shops": [{"platform": p, "shop_id": container.settings.shop_id} for p in platforms],
        "windows": ["今日", "昨日", "近 7 日", "近 30 日"],
        "metric_versions": [f"v{version}" for version in metric_versions] or ["v1"],
        "role": user.role.value,
        "readonly": container.settings.readonly_mode,
        "platform_gate_max": container.settings.platform_gate_max.value,
        "default": {
            "platform": container.settings.platform_source or container.settings.platform,
            "shop_id": container.settings.shop_id,
            "window": "昨日",
        },
    }


@router.get("/workbench/nav")
def nav(
    container: AppContainer = Depends(get_container),
    user: SessionUser = Depends(get_current_user),
) -> dict[str, Any]:
    pages: list[dict[str, Any]] = []
    for page in PAGES:
        if user.role.value not in page["roles"]:
            continue
        cards = [
            c
            for c in container.registry.by_kind("WorkbenchCard")
            if c.config.get("page_id") == page["page_id"]
        ]
        available = bool(cards) or page["page_id"] in KERNEL_CARDS or page["page_id"] in {
            "P05",
            "P06",
        }
        pages.append(
            {
                **page,
                "available": available,
                "card_ids": [c.config.get("card_id", c.id) for c in cards]
                + [c["card_id"] for c in KERNEL_CARDS.get(page["page_id"], [])],
            }
        )
    return {"pages": pages, "readonly": container.settings.readonly_mode}


@router.get("/workbench/cards")
def cards(
    page: str = Query(default="P01", pattern=r"^P\d{2}$"),
    container: AppContainer = Depends(get_container),
    user: SessionUser = Depends(get_current_user),
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for contribution in container.registry.by_kind("WorkbenchCard"):
        config = contribution.config
        if config.get("page_id") != page:
            continue
        items.append(
            {
                "card_id": config.get("card_id", contribution.id),
                "page_id": page,
                "module": contribution.module,
                "title": config.get("title", contribution.id),
                "slot": config.get("slot", "main"),
                "data_endpoint": config.get("data_endpoint", ""),
                "empty_state_copy": config.get("empty_state_copy", "暂无可展示内容"),
                "order": config.get("order", 100),
            }
        )
    items.extend(KERNEL_CARDS.get(page, []))
    items.sort(key=lambda item: item.get("order", 100))
    return {"page_id": page, "cards": items, "readonly": container.settings.readonly_mode}


@router.get("/reports/latest")
def latest_report(
    platform: str | None = Query(default=None),
    shop_id: str | None = Query(default=None),
    container: AppContainer = Depends(get_container),
    user: SessionUser = Depends(get_current_user),
) -> dict[str, Any]:
    platform = platform or container.settings.platform_source or container.settings.platform
    shop_id = shop_id or container.settings.shop_id
    assert_shop_scope(user, platform, shop_id)
    report = _latest_report(container, platform, shop_id)
    if report is None:
        return {
            "report_id": None,
            "run_id": None,
            "platform": platform,
            "shop_id": shop_id,
            "window": None,
            "window_label": "",
            "metric_version": "v1",
            "channel": None,
            "channel_label": "",
            "data_state": "EMPTY",
            "empty_copy": "该时间窗暂无数据（非取数失败）",
            "columns": [],
            "rows": [],
            "alerts": [],
            "readonly": container.settings.readonly_mode,
            "watermark": "",
            "generated_at": None,
        }
    return _report_payload(container, report.report_id, user)


@router.get("/reports/{report_id}")
def report_detail(
    report_id: str,
    container: AppContainer = Depends(get_container),
    user: SessionUser = Depends(get_current_user),
) -> dict[str, Any]:
    report = container.reports.get(report_id)
    if report is None:
        raise DomainError("E008", f"报表不存在: {report_id}", status_override=404)
    assert_shop_scope(user, report.platform, report.shop_id)
    return _report_payload(container, report_id, user)


@router.get("/reports/{report_id}/export")
def export_report(
    report_id: str,
    container: AppContainer = Depends(get_container),
    user: SessionUser = Depends(get_current_user),
) -> Response:
    if not user.can(Permission.EXPORT_REPORT):
        raise DomainError("E003", "当前角色不能导出报表")
    report = container.reports.get(report_id)
    if report is None:
        raise DomainError("E008", f"报表不存在: {report_id}", status_override=404)
    assert_shop_scope(user, report.platform, report.shop_id)
    data = container.storage.get_bytes(report.artifact_ref)
    container.audit.record(
        AuditEntry(
            actor=user.username,
            action="report.export",
            object_type="report",
            object_id=report.report_id,
            after={"run_id": report.run_id.value, "watermark": report.watermark},
        )
    )
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{report.report_id}.xlsx"',
        },
    )


@router.get("/metric-cards/{metric_code}")
def metric_card(
    metric_code: str,
    container: AppContainer = Depends(get_container),
    user: SessionUser = Depends(get_current_user),
) -> dict[str, Any]:
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
    latest = _latest_report(
        container,
        container.settings.platform_source or container.settings.platform,
        container.settings.shop_id,
    )
    last_value = None
    evidence_refs: list[str] = []
    if latest is not None:
        rows = container.dws.by_run(latest.run_id)
        for row in rows:
            if row["metric_code"] == metric_code:
                last_value = {
                    "value": str(row["value"]) if row["value"] is not None else None,
                    "null_reason": row["null_reason"],
                    "stat_date": row["stat_date"].isoformat(),
                }
        evidence_refs = [
            item["payload_hash"] for item in container.ods.by_run(latest.run_id)
        ]
    return {
        "id": f"metric.{definition.metric_code}",
        "name": definition.display_name,
        "metric_code": definition.metric_code,
        "version": definition.version,
        "status": "RELEASED",
        "owner": "studio",
        "domain": "BC-3",
        "effective_from": definition.effective_from,
        "breaking_change": definition.breaking_change,
        "business_question": definition.description,
        "concept_uri": definition.concept_uri,
        "synonyms": list(definition.synonyms),
        "display_name": definition.display_name,
        "compute": {
            "formula": definition.formula,
            "denominator": definition.denominator,
            "unit": definition.unit,
            "precision": definition.precision,
            "additivity": definition.additivity.value,
            "null_policy": definition.null_policy.name,
            "source_mapping": definition.source_mapping,
        },
        "quality": {
            "quality_tests": list(definition.quality_tests),
            "release_gate_passed": bool(card and card.get("release_gate_passed")),
        },
        "evidence": {
            "probe_sql_template": definition.probe_sql_template,
            "last_inspected_value": last_value,
            "ods_refs": evidence_refs,
            "run_id": latest.run_id.value if latest else None,
        },
        "card": card["card"] if card else None,
        "readonly": container.settings.readonly_mode,
    }


@router.get("/runs/{run_id}")
def run_detail(
    run_id: str,
    container: AppContainer = Depends(get_container),
    user: SessionUser = Depends(get_current_user),
) -> dict[str, Any]:
    from shared.run_id import RunId

    run = container.runs.get(RunId.parse(run_id))
    if run is None:
        raise DomainError("E008", f"运行不存在: {run_id}", status_override=404)
    assert_shop_scope(user, run.platform, run.shop_id)
    reports = [r for r in container.reports.recent(50) if r.run_id == run.run_id]
    return {
        "run_id": run.run_id.value,
        "app_id": run.app_id,
        "scene": run.scene,
        "platform": run.platform,
        "shop_id": run.shop_id,
        "window": {"start": run.window.start.isoformat(), "end": run.window.end.isoformat()},
        "status": run.status.value,
        "gate_level_max": run.gate_level_max.value,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "ended_at": run.ended_at.isoformat() if run.ended_at else None,
        "err_code": run.err_code,
        "err_layer": run.err_layer,
        "config_snapshot_hash": run.config_snapshot.hash,
        "config_snapshot": run.config_view(),
        "nodes": [
            {
                "node_id": node.node_id,
                "status": node.status.value,
                "cost_ms": node.cost_ms,
                "channel": node.channel.value if node.channel else None,
                "err_code": node.err_code,
                "err_layer": node.err_layer,
                "payload_digest": node.payload_digest,
            }
            for node in run.nodes
        ],
        "ods": [
            {
                "id": item["id"],
                "dataset": item["dataset"],
                "channel": item["channel"],
                "payload_hash": item["payload_hash"],
                "record_count": item["record_count"],
                "fetched_at": item["fetched_at"],
            }
            for item in container.ods.by_run(run.run_id)
        ],
        "reports": [
            {
                "report_id": report.report_id,
                "metric_version": report.metric_version,
                "artifact_ref": report.artifact_ref,
                "generated_at": report.generated_at.isoformat(),
            }
            for report in reports
        ],
        "exceptions": [
            item
            for item in container.exceptions.recent(50)
            if item.get("run_id") == run.run_id.value
        ],
    }


@router.get("/runs/{run_id}/evidence/{payload_id}")
def run_evidence(
    run_id: str,
    payload_id: int,
    raw: bool = Query(default=False),
    container: AppContainer = Depends(get_container),
    user: SessionUser = Depends(get_current_user),
) -> dict[str, Any]:
    item = container.ods.get(payload_id)
    if item is None or item["run_id"] != run_id:
        raise DomainError("E008", f"证据不存在: {payload_id}", status_override=404)
    if raw:
        if not Desensitizer.can_view_raw(user.role.value):
            raise DomainError("E003", "原文证据仅审计角色可见")
        container.audit.record(
            AuditEntry(
                actor=user.username,
                action="evidence.raw_access",
                object_type="ods_payload",
                object_id=str(payload_id),
                reason="审计角色查看原文",
                after={"run_id": run_id, "dataset": item["dataset"]},
            )
        )
        payload = item["payload"]
        masked = False
    else:
        payload = Desensitizer().mask_log(item["payload"])
        masked = True
    return {
        "id": item["id"],
        "run_id": item["run_id"],
        "dataset": item["dataset"],
        "channel": item["channel"],
        "payload_hash": item["payload_hash"],
        "record_count": item["record_count"],
        "fetched_at": item["fetched_at"],
        "masked": masked,
        "masked_copy": "买家信息已脱敏，原文证据仅审计角色可见",
        "payload": payload,
    }


@router.get("/todos")
def todos(
    type: str | None = Query(default=None),
    container: AppContainer = Depends(get_container),
    user: SessionUser = Depends(get_current_user),
) -> dict[str, Any]:
    now = _now()
    items: list[dict[str, Any]] = []
    for task in container.approvals.recent(50):
        remaining = int((task.sla_expires_at - now).total_seconds())
        items.append(
            {
                "todo_id": task.task_id,
                "type": "TODO-APPROVAL",
                "title": f"{task.action_code or task.scene} · {task.platform}/{task.shop_id}",
                "status": task.status.value,
                "gate_level": task.gate_level.value,
                "sla_expires_at": task.sla_expires_at.isoformat(),
                "remaining_seconds": remaining,
                "overdue": remaining <= 0 and task.status.value == "PENDING",
                "href": f"/change-orders/{task.change_order_no or task.task_id}",
                "module": "mod_gate",
                "approver": task.approver,
                "created_at": task.write_plan.get("created_at"),
            }
        )
    for ticket in container.review_tickets.list(limit=100):
        if ticket["status"] == "CLOSED":
            continue
        due = ticket.get("sla_due_at")
        remaining = (
            int((datetime.fromisoformat(due) - now).total_seconds()) if due else None
        )
        items.append(
            {
                "todo_id": ticket["ticket_id"],
                "type": "TODO-REVIEW",
                "title": f"{ticket['severity']} · {ticket['sku'] or ticket['review_id']} · {ticket['hit_rule']}",
                "status": ticket["status"],
                "gate_level": "L1",
                "sla_expires_at": due,
                "remaining_seconds": remaining,
                "overdue": remaining is not None and remaining <= 0,
                "href": f"/reviews/tickets/{ticket['ticket_id']}",
                "module": "mod_review_patrol",
                "created_at": ticket.get("created_at"),
            }
        )
    latest_stock_run = next(
        (item for item in container.runs.recent(50) if item.scene == "S07"), None
    )
    stock_suggestions = (
        container.stock.by_run(latest_stock_run.run_id)["suggestions"]
        if latest_stock_run is not None
        else []
    )
    for suggestion in stock_suggestions:
        if suggestion["status"] != "OPEN":
            continue
        items.append(
            {
                "todo_id": suggestion["suggestion_id"],
                "type": "TODO-STOCK",
                "title": f"{suggestion['action']} · {suggestion['sku']} · {suggestion['reason'][:40]}",
                "status": suggestion["status"],
                "gate_level": "L1",
                "sla_expires_at": None,
                "remaining_seconds": None,
                "overdue": False,
                "href": f"/p03?sku={suggestion['sku']}",
                "module": "mod_stock_recon",
                "created_at": suggestion.get("created_at"),
            }
        )
    for exception in container.exceptions.recent(50):
        items.append(
            {
                "todo_id": f"exc_{exception['id']}",
                "type": "TODO-EXCEPTION",
                "title": f"{exception['err_code']}/{exception['err_layer']} · {exception['message'][:40]}",
                "status": exception["status"],
                "gate_level": None,
                "sla_expires_at": None,
                "remaining_seconds": None,
                "overdue": False,
                "href": f"/runs/{exception['run_id']}" if exception["run_id"] else None,
                "module": "mod_audit",
                "created_at": exception["created_at"],
            }
        )
    if type:
        items = [item for item in items if item["type"] == type]
    counts: dict[str, int] = {}
    for item in items:
        counts[item["type"]] = counts.get(item["type"], 0) + 1
    return {"items": items, "counts": counts, "readonly": container.settings.readonly_mode}


@router.get("/change-orders/{change_order_no}")
def change_order(
    change_order_no: str,
    container: AppContainer = Depends(get_container),
    user: SessionUser = Depends(get_current_user),
) -> dict[str, Any]:
    order = container.change_orders.get(change_order_no)
    task = container.approvals.get(change_order_no)
    if order is None and task is None:
        raise DomainError("E008", f"变更单不存在: {change_order_no}", status_override=404)
    if task is None and order is not None:
        task = container.approvals.get(order["task_id"])
    if task is None:
        raise DomainError("E008", "变更单缺少审批任务")
    assert_shop_scope(user, task.platform, task.shop_id)
    plan_data = task.write_plan or {}
    write_plan = (
        container.write_plans.get(str(plan_data.get("plan_id")))
        if plan_data.get("plan_id")
        else None
    )
    executions = (
        container.write_executions.by_plan(write_plan.plan_id) if write_plan else []
    )
    latest_execution = executions[-1] if executions else None
    rows = write_plan.rows if write_plan else plan_data.get("rows", [])
    ceiling_allows = container.settings.platform_gate_max.rank >= 2
    pending = task.status.value == "PENDING" and (
        write_plan is None or write_plan.status.value == "PENDING_APPROVAL"
    )
    can_approve = bool(
        pending
        and ceiling_allows
        and write_plan is not None
        and user.can(Permission.APPROVE_L2)
    )
    if not ceiling_allows:
        readonly_copy = "需审批后执行（当前只读模式）"
    elif not user.can(Permission.APPROVE_L2):
        readonly_copy = "需审批后执行（当前角色无审批权限）"
    else:
        readonly_copy = "该变更单已处理，如需修改请重新发起"

    timeline = [
        {"state": "PENDING", "at": plan_data.get("created_at"), "label": "待确认"},
    ]
    if task.evidence is not None:
        timeline.append(
            {
                "state": "APPROVED",
                "at": task.evidence.decided_at.isoformat(),
                "label": f"已批准（{task.evidence.operator}）",
            }
        )
    if latest_execution is not None:
        timeline.append(
            {
                "state": latest_execution.status,
                "at": latest_execution.started_at.isoformat()
                if latest_execution.started_at
                else None,
                "label": {
                    "VERIFIED": "已执行并回查一致",
                    "FAILED": "执行失败（已进入补偿评估）",
                }.get(latest_execution.status, latest_execution.status),
            }
        )
    if task.status.value in {"EXPIRED", "REJECTED", "WITHDRAWN", "COMPENSATED"}:
        timeline.append(
            {
                "state": task.status.value,
                "at": None,
                "label": {
                    "EXPIRED": "超时自动作废，未执行",
                    "REJECTED": "已驳回，不自动重试",
                    "WITHDRAWN": "已撤回，未执行",
                    "COMPENSATED": "已补偿",
                }[task.status.value],
            }
        )
    return {
        "change_order_no": task.change_order_no or change_order_no,
        "task_id": task.task_id,
        "plan_id": write_plan.plan_id if write_plan else plan_data.get("plan_id"),
        "status": task.status.value,
        "plan_status": write_plan.status.value if write_plan else None,
        "header": {
            "scene": task.scene,
            "platform": task.platform,
            "shop_id": task.shop_id,
            "requested_by": task.requested_by,
            "approver": task.approver,
            "created_at": plan_data.get("created_at"),
            "gate_level": task.gate_level.value,
            "write_plan_hash": task.write_plan_hash,
            "metric_version": plan_data.get("metric_version"),
            "snapshot_time": plan_data.get("snapshot_time"),
            "schema_version": plan_data.get("schema_version", "1.0"),
            "sla_expires_at": task.sla_expires_at.isoformat(),
        },
        "before_after": rows,
        "impact_scope": task.impact_scope,
        "evidence": write_plan.evidence if write_plan else plan_data.get("evidence", []),
        "rollback_plan": write_plan.rollback_plan if write_plan else plan_data.get("rollback_plan"),
        "evidence_complete": (
            task.evidence.approvable() if task.evidence else bool(plan_data.get("evidence"))
        ),
        "readonly": not can_approve,
        "can_approve": can_approve,
        "readonly_copy": readonly_copy,
        "execution": (
            {
                "execution_id": latest_execution.execution_id,
                "status": latest_execution.status,
                "before_shot": latest_execution.before_shot,
                "after_shot": latest_execution.after_shot,
                "verify_result": latest_execution.verify_result,
                "err_code": latest_execution.err_code,
                "err_layer": latest_execution.err_layer,
                "ended_at": latest_execution.ended_at.isoformat()
                if latest_execution.ended_at
                else None,
            }
            if latest_execution
            else None
        ),
        "result_timeline": timeline,
    }


@router.post("/change-orders/{task_id}/transfer")
def transfer_change_order(
    task_id: str,
    body: TransferRequest,
    container: AppContainer = Depends(get_container),
    user: SessionUser = Depends(require(Permission.APPROVE_L2)),
) -> dict[str, Any]:
    task = container.approvals.get(task_id)
    if task is None:
        raise DomainError("E008", f"变更单不存在: {task_id}", status_override=404)
    assert_shop_scope(user, task.platform, task.shop_id)
    task.transfer_to(body.approver, _now())
    container.approvals.save(task)
    container.audit.record(
        AuditEntry(
            actor=user.username,
            action="approval.transfer",
            object_type="approval_task",
            object_id=task.task_id,
            reason=body.reason or None,
            after={"approver": task.approver, "sla_expires_at": task.sla_expires_at.isoformat()},
        )
    )
    container.notifier.send(
        event="EVT-05",
        receiver=task.approver,
        title=f"变更单已转交 · {task.action_code}",
        body=f"{user.username} 将 {task.task_id} 转交给你审批，SLA 重新计时",
        dedupe_key=f"EVT-05:transfer:{task.task_id}:{task.approver}",
    )
    return {
        "task_id": task.task_id,
        "status": task.status.value,
        "approver": task.approver,
        "sla_expires_at": task.sla_expires_at.isoformat(),
    }


@router.get("/modules")
def modules(
    container: AppContainer = Depends(get_container),
    user: SessionUser = Depends(get_current_user),
) -> dict[str, Any]:
    with container.database.session() as session:
        states = session.execute(select(ModuleStateRow)).scalars().all()
    contribution_map: dict[str, list[dict[str, str]]] = {}
    for key, module in container.registry.all_ids().items():
        kind, contrib_id = key.split("/", 1)
        contribution_map.setdefault(module, []).append({"kind": kind, "id": contrib_id})
    blocked = []
    bundles: list[dict[str, Any]] = []
    if container.startup_report is not None:
        blocked = [
            {"module": i.module, "check": i.check, "reason": i.message}
            for i in container.startup_report.blocked
        ]
        bundles = [
            {
                "name": state.name,
                "version": state.version,
                "state": state.state,
                "depends": state.depends,
            }
            for state in container.startup_report.states
            if state.category == "bundle"
        ]
    return {
        "modules": [
            {
                "name": state.name,
                "version": state.version,
                "category": state.category,
                "state": state.state,
                "enabled": state.enabled,
                "blocking_reason": state.blocking_reason,
                "contributions": contribution_map.get(state.name, []),
                "core": state.category == "core",
            }
            for state in sorted(states, key=lambda s: (s.category, s.name))
        ],
        "blocked": blocked,
        "bundles": bundles,
        "kernel_api": "1.0",
        "platform_gate_max": container.settings.platform_gate_max.value,
        "readonly": container.settings.platform_gate_max.rank < 2,
    }


@router.post("/modules/{name}/disable")
def disable_module(
    name: str,
    container: AppContainer = Depends(get_container),
    user: SessionUser = Depends(require_owner),
) -> dict[str, Any]:
    with container.database.session() as session:
        row = session.get(ModuleStateRow, name)
        if row is None:
            raise DomainError("E008", f"模块不存在: {name}", status_override=404)
        if row.category == "core":
            raise DomainError("E007", f"模块 {name} 为 core，不可禁用")
        row.enabled = False
    disabled = set(container.registry.disabled_modules()) | {name}
    container.registry.set_disabled(disabled)
    container.audit.record(
        AuditEntry(
            actor=user.username,
            action="module.disable",
            object_type="module",
            object_id=name,
            after={"enabled": False},
        )
    )
    return {"module": name, "enabled": False, "note": "已摘除该模块的卡片/调度/路由贡献"}


@router.post("/modules/{name}/enable")
def enable_module(
    name: str,
    container: AppContainer = Depends(get_container),
    user: SessionUser = Depends(require_owner),
) -> dict[str, Any]:
    with container.database.session() as session:
        row = session.get(ModuleStateRow, name)
        if row is None:
            raise DomainError("E008", f"模块不存在: {name}", status_override=404)
        row.enabled = True
    container.audit.record(
        AuditEntry(
            actor=user.username,
            action="module.enable",
            object_type="module",
            object_id=name,
            after={"enabled": True},
        )
    )
    return {
        "module": name,
        "enabled": True,
        "note": "重新启用需要重启控制面完成装配（M1 再做运行时热装载）",
    }


@router.get("/approvals/history")
def approvals_history(
    limit: int = Query(default=50, ge=1, le=200),
    status: str | None = Query(default=None),
    action_code: str | None = Query(default=None),
    approver: str | None = Query(default=None),
    container: AppContainer = Depends(get_container),
    user: SessionUser = Depends(require(Permission.VIEW_AUDIT)),
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for task in container.approvals.recent(200):
        if status and task.status.value != status:
            continue
        if action_code and task.action_code != action_code:
            continue
        if approver and task.approver != approver:
            continue
        plan = (
            container.write_plans.get(str(task.write_plan.get("plan_id")))
            if task.write_plan.get("plan_id")
            else None
        )
        executions = container.write_executions.by_plan(plan.plan_id) if plan else []
        latest = executions[-1] if executions else None
        items.append(
            {
                "task_id": task.task_id,
                "change_order_no": task.change_order_no,
                "plan_id": plan.plan_id if plan else None,
                "action_code": task.action_code,
                "scene": task.scene,
                "platform": task.platform,
                "shop_id": task.shop_id,
                "status": task.status.value,
                "plan_status": plan.status.value if plan else None,
                "execution_status": latest.status if latest else None,
                "approver": task.approver,
                "requested_by": task.requested_by,
                "rows": len(plan.rows) if plan else len(task.write_plan.get("rows", [])),
                "sla_expires_at": task.sla_expires_at.isoformat(),
                "created_at": task.write_plan.get("created_at"),
            }
        )
        if len(items) >= limit:
            break
    counts: dict[str, int] = {}
    for item in items:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    return {
        "items": items,
        "counts": counts,
        "empty_copy": "该时间窗无审批记录",
    }


@router.get("/platform/price-list")
def platform_price_list(
    container: AppContainer = Depends(get_container),
    user=Depends(get_current_user),
) -> dict[str, Any]:
    path = container.settings.storage_dir / "platform_state" / "demo_prices.json"
    items: list[dict[str, str]] = []
    if path.is_file():
        try:
            import json

            data = json.loads(path.read_text(encoding="utf-8"))
            items = [
                {"sku": str(sku), "price": str(price)}
                for sku, price in sorted(data.items())
            ]
        except (OSError, ValueError):
            items = []
    return {
        "items": items,
        "campaign_suggestions": ["C-618", "C-1111", "C-1212"],
        "demo_only": True,
        "note": "演示平台价格来自本地受控状态；真实商品清单由平台接口提供",
    }


@router.get("/audit")
def audit_log(
    limit: int = Query(default=50, ge=1, le=200),
    action: str | None = Query(default=None),
    actor: str | None = Query(default=None),
    object_type: str | None = Query(default=None),
    object_id: str | None = Query(default=None),
    since: str | None = Query(default=None, alias="from"),
    until: str | None = Query(default=None, alias="to"),
    container: AppContainer = Depends(get_container),
    user: SessionUser = Depends(require(Permission.VIEW_AUDIT)),
) -> dict[str, Any]:
    try:
        since_at = datetime.fromisoformat(since) if since else None
        until_at = datetime.fromisoformat(until) if until else None
    except ValueError as exc:
        raise DomainError("E006", f"时间过滤参数不是合法 ISO 时间: {exc}") from exc
    return {
        "items": container.audit.recent(
            limit=limit,
            action=action,
            actor=actor,
            object_type=object_type,
            object_id=object_id,
            since=since_at,
            until=until_at,
        ),
        "filters": {
            "action": action,
            "actor": actor,
            "object_type": object_type,
            "object_id": object_id,
            "from": since,
            "to": until,
        },
    }


@router.get("/workers")
def workers(
    container: AppContainer = Depends(get_container),
    user: SessionUser = Depends(get_current_user),
) -> dict[str, Any]:
    items = [
        {
            "worker_id": worker.worker_id,
            "kind": worker.kind.value,
            "status": worker.status.value,
            "capabilities": worker.capabilities,
            "queue_depth": worker.queue_depth,
            "last_heartbeat_at": worker.last_heartbeat_at.isoformat()
            if worker.last_heartbeat_at
            else None,
        }
        for worker in container.workers.list()
    ]
    return {
        "items": items,
        "online": len([w for w in items if w["status"] != "OFFLINE"]),
        "empty_copy": "暂无在线机器人",
    }


@router.get("/exceptions")
def exceptions(
    limit: int = Query(default=50, ge=1, le=200),
    container: AppContainer = Depends(get_container),
    user: SessionUser = Depends(get_current_user),
) -> dict[str, Any]:
    return {"items": container.exceptions.recent(limit)}


@router.get("/healthz")
def healthz(container: AppContainer = Depends(get_container)) -> dict[str, Any]:
    return {
        "status": "ok",
        "env": container.settings.env,
        "readonly": container.settings.readonly_mode,
        "modules_loaded": len(container.startup_report.loaded) if container.startup_report else 0,
        "platform_gate_max": container.settings.platform_gate_max.value,
    }


@router.get("/readyz")
def readyz(container: AppContainer = Depends(get_container)) -> dict[str, Any]:
    if not container.adapters:
        raise DomainError("E008", "没有可用平台适配器")
    return {"status": "ready", "adapters": sorted(container.adapters)}
