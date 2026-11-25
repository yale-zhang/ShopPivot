"""P02 评价巡检 / P03 库存对账读接口（M1）。"""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from bootstrap.container import AppContainer
from bootstrap.deps import get_container, get_current_user, require
from kernel.contexts.identity.domain.account import Permission
from kernel.contexts.observability.domain.models import AuditEntry
from shared.errors.registry import DomainError
from shared.run_id import RunId

router = APIRouter(prefix="/api/v1", tags=["ops"])


def _now() -> datetime:
    return datetime.now(UTC)


class AssignRequest(BaseModel):
    assignee: str = Field(min_length=1, max_length=64)


class CloseRequest(BaseModel):
    resolution: str = Field(min_length=1, max_length=500)


class SuggestionActionRequest(BaseModel):
    note: str = Field(default="", max_length=255)


@router.get("/reviews/tickets")
def list_review_tickets(
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
    container: AppContainer = Depends(get_container),
    user=Depends(get_current_user),
) -> dict:
    if status and status not in {"OPEN", "ASSIGNED", "CLOSED"}:
        raise DomainError("E006", f"未知工单状态: {status}")
    now = _now()
    items = container.review_tickets.list(status=status, limit=limit)
    for item in items:
        due = item.get("sla_due_at")
        if due:
            due_at = datetime.fromisoformat(due)
            item["remaining_seconds"] = int((due_at - now).total_seconds())
            item["overdue"] = item["status"] != "CLOSED" and item["remaining_seconds"] <= 0
        else:
            item["remaining_seconds"] = None
            item["overdue"] = False
    counts: dict[str, int] = {}
    for item in items:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    return {
        "items": items,
        "counts": counts,
        "empty_copy": "暂无差评或问答待处理",
        "readonly": container.settings.readonly_mode,
    }


@router.get("/reviews/summary")
def review_summary(
    container: AppContainer = Depends(get_container),
    user=Depends(get_current_user),
) -> dict:
    platform = container.settings.platform_source or container.settings.platform
    shop_id = container.settings.shop_id
    tickets = container.review_tickets.list(limit=200)
    counts: dict[str, int] = {}
    for ticket in tickets:
        counts[ticket["status"]] = counts.get(ticket["status"], 0) + 1
    now = _now()
    overdue = sum(
        1
        for ticket in tickets
        if ticket["status"] != "CLOSED"
        and ticket.get("sla_due_at")
        and datetime.fromisoformat(ticket["sla_due_at"]) <= now
    )
    return {
        "platform": platform,
        "shop_id": shop_id,
        "counts": counts,
        "open": counts.get("OPEN", 0),
        "assigned": counts.get("ASSIGNED", 0),
        "closed": counts.get("CLOSED", 0),
        "overdue": overdue,
        "trend": container.dwd.review_trend(platform, shop_id, limit=14),
        "empty_copy": "暂无差评或问答待处理",
    }


@router.post("/reviews/tickets/{ticket_id}/assign")
def assign_ticket(
    ticket_id: str,
    body: AssignRequest,
    container: AppContainer = Depends(get_container),
    user=Depends(require(Permission.HANDLE_TODO)),
) -> dict:
    ticket = container.review_tickets.get(ticket_id)
    if ticket is None:
        raise DomainError("E008", f"工单不存在: {ticket_id}", status_override=404)
    try:
        ticket.assign(body.assignee)
    except ValueError as exc:
        raise DomainError("E006", str(exc)) from exc
    container.review_tickets.save(ticket)
    container.audit.record(
        AuditEntry(
            actor=user.username,
            action="review.assign",
            object_type="review_ticket",
            object_id=ticket_id,
            after={"assignee": body.assignee, "status": ticket.status.value},
        )
    )
    return {"ticket_id": ticket_id, "status": ticket.status.value, "assignee": body.assignee}


@router.post("/reviews/tickets/{ticket_id}/close")
def close_ticket(
    ticket_id: str,
    body: CloseRequest,
    container: AppContainer = Depends(get_container),
    user=Depends(require(Permission.HANDLE_TODO)),
) -> dict:
    ticket = container.review_tickets.get(ticket_id)
    if ticket is None:
        raise DomainError("E008", f"工单不存在: {ticket_id}", status_override=404)
    try:
        ticket.close(body.resolution)
    except ValueError as exc:
        raise DomainError("E006", str(exc)) from exc
    container.review_tickets.save(ticket)
    container.audit.record(
        AuditEntry(
            actor=user.username,
            action="review.close",
            object_type="review_ticket",
            object_id=ticket_id,
            reason=body.resolution,
            after={"status": ticket.status.value},
        )
    )
    return {"ticket_id": ticket_id, "status": ticket.status.value}


@router.get("/settlement/reconciliation")
def settlement_reconciliation(
    run_id: str | None = Query(default=None),
    diff_type: str | None = Query(default=None),
    container: AppContainer = Depends(get_container),
    user=Depends(get_current_user),
) -> dict:
    run = None
    if run_id:
        run = container.runs.get(RunId.parse(run_id))
        if run is None:
            raise DomainError("E008", f"运行不存在: {run_id}", status_override=404)
    else:
        run = next(
            (item for item in container.runs.recent(50) if item.scene == "S09"), None
        )
    if run is None:
        return {
            "run_id": None,
            "window": None,
            "diffs": [],
            "counts": {},
            "totals": {"expected": 0, "settled": 0, "delta": 0},
            "note": "财务写入禁止（L3）；差异逐条可追溯双边凭据",
            "empty_copy": "无差异",
            "readonly": True,
        }
    diffs = container.settlements.by_run(run.run_id)
    if diff_type:
        diffs = [item for item in diffs if item["diff_type"] == diff_type]
    counts: dict[str, int] = {}
    expected = 0.0
    settled = 0.0
    delta = 0.0
    for item in diffs:
        counts[item["diff_type"]] = counts.get(item["diff_type"], 0) + 1
        expected += item["expected_net"]
        settled += item["settled_amount"] or 0.0
        delta += item["delta"]
    return {
        "run_id": run.run_id.value,
        "window": {"start": run.window.start.isoformat(), "end": run.window.end.isoformat()},
        "diffs": diffs,
        "counts": counts,
        "totals": {
            "expected": round(expected, 2),
            "settled": round(settled, 2),
            "delta": round(delta, 2),
        },
        "note": "财务写入禁止（L3）；差异逐条可追溯双边凭据",
        "empty_copy": "无差异",
        "readonly": True,
    }


@router.get("/ads/summary")
def ads_summary(
    run_id: str | None = Query(default=None),
    container: AppContainer = Depends(get_container),
    user=Depends(get_current_user),
) -> dict:
    run = None
    if run_id:
        run = container.runs.get(RunId.parse(run_id))
        if run is None:
            raise DomainError("E008", f"运行不存在: {run_id}", status_override=404)
    else:
        run = next(
            (item for item in container.runs.recent(50) if item.scene == "S04"), None
        )
    if run is None:
        return {
            "run_id": None,
            "window": None,
            "campaigns": [],
            "counts": {},
            "totals": {"cost": 0, "revenue": 0, "roi": None},
            "note": "只出建议，不自动调价 / 不自动调预算",
            "empty_copy": "当前无投放数据",
            "readonly": container.settings.readonly_mode,
        }
    campaigns = container.ads.by_run(run.run_id)
    counts: dict[str, int] = {}
    cost = 0.0
    revenue = 0.0
    for row in campaigns:
        counts[row["alert_level"]] = counts.get(row["alert_level"], 0) + 1
        cost += row["cost"]
        revenue += row["revenue"]
    return {
        "run_id": run.run_id.value,
        "window": {"start": run.window.start.isoformat(), "end": run.window.end.isoformat()},
        "campaigns": campaigns,
        "counts": counts,
        "totals": {
            "cost": round(cost, 2),
            "revenue": round(revenue, 2),
            "roi": round(revenue / cost, 2) if cost > 0 else None,
        },
        "note": "只出建议，不自动调价 / 不自动调预算",
        "empty_copy": "当前无投放数据",
        "readonly": container.settings.readonly_mode,
    }


@router.get("/inventory/reconciliation")
def inventory_reconciliation(
    run_id: str | None = Query(default=None),
    container: AppContainer = Depends(get_container),
    user=Depends(get_current_user),
) -> dict:
    run = None
    if run_id:
        run = container.runs.get(RunId.parse(run_id))
    else:
        run = next(
            (item for item in container.runs.recent(50) if item.scene == "S07"), None
        )
    if run is None:
        return {
            "run_id": None,
            "window": None,
            "diffs": [],
            "suggestions": [],
            "counts": {},
            "snapshot_note": "三方库存一致，无差异",
            "empty_copy": "三方库存一致，无差异",
            "readonly": container.settings.readonly_mode,
        }
    payload = container.stock.by_run(run.run_id)
    counts: dict[str, int] = {}
    for diff in payload["diffs"]:
        counts[diff["diff_type"]] = counts.get(diff["diff_type"], 0) + 1
    return {
        "run_id": run.run_id.value,
        "window": {"start": run.window.start.isoformat(), "end": run.window.end.isoformat()},
        "diffs": payload["diffs"],
        "suggestions": payload["suggestions"],
        "counts": counts,
        "snapshot_note": "平台/ERP/WMS 快照时间分别标注，时间窗不一致时不强行合并",
        "empty_copy": "三方库存一致，无差异",
        "readonly": container.settings.readonly_mode,
    }


@router.get("/inventory/suggestions")
def list_stock_suggestions(
    status: str | None = Query(default=None),
    container: AppContainer = Depends(get_container),
    user=Depends(get_current_user),
) -> dict:
    items = container.stock.suggestions(status=status)
    return {"items": items, "empty_copy": "暂无补货建议"}


@router.post("/inventory/suggestions/{suggestion_id}/accept")
def accept_stock_suggestion(
    suggestion_id: str,
    body: SuggestionActionRequest,
    container: AppContainer = Depends(get_container),
    user=Depends(require(Permission.HANDLE_TODO)),
) -> dict:
    return _resolve_suggestion(container, user.username, suggestion_id, "ACCEPTED", body.note)


@router.post("/inventory/suggestions/{suggestion_id}/ignore")
def ignore_stock_suggestion(
    suggestion_id: str,
    body: SuggestionActionRequest,
    container: AppContainer = Depends(get_container),
    user=Depends(require(Permission.HANDLE_TODO)),
) -> dict:
    return _resolve_suggestion(container, user.username, suggestion_id, "IGNORED", body.note)


def _resolve_suggestion(
    container: AppContainer, actor: str, suggestion_id: str, status: str, note: str
) -> dict:
    if not container.stock.resolve_suggestion(suggestion_id, status):
        raise DomainError("E008", f"补货建议不存在: {suggestion_id}", status_override=404)
    container.audit.record(
        AuditEntry(
            actor=actor,
            action=f"stock.suggestion.{status.lower()}",
            object_type="stock_suggestion",
            object_id=suggestion_id,
            reason=note or None,
            after={"status": status},
        )
    )
    return {"suggestion_id": suggestion_id, "status": status, "note": note}
