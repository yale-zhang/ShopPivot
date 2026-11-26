"""P13 1688 选品与采购接口。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from bootstrap.container import AppContainer, run_scene
from bootstrap.deps import get_container, get_current_user
from kernel.contexts.observability.domain.models import AuditEntry
from shared.errors.registry import DomainError
from kernel.contexts.metric_data.domain.purchase import PurchaseStatus
from kernel.contexts.skill.domain.models import SkillUnavailable
from shared.run_id import RunId

router = APIRouter(prefix="/api/v1", tags=["1688"])


class SourcingSearchRequest(BaseModel):
    keyword: str = Field(min_length=1, max_length=64)
    limit: int = Field(default=20, ge=1, le=50)
    filters: list[dict[str, Any]] = Field(default_factory=list)


@router.post("/sourcing/search")
def sourcing_search(
    body: SourcingSearchRequest,
    container: AppContainer = Depends(get_container),
    user=Depends(get_current_user),
) -> dict[str, Any]:
    result = run_scene(
        container,
        "S10",
        requested_by=user.username,
        trigger_type="MANUAL",
        params={"keyword": body.keyword, "limit": body.limit, "filters": body.filters},
    )
    run = result.run
    candidates = (
        container.sourcing.by_run(run.run_id) if run.status.value == "SUCCEEDED" else []
    )
    payload = {
        "run_id": run.run_id.value,
        "status": run.status.value,
        "keyword": body.keyword,
        "candidates": candidates,
        "count": len(candidates),
        "empty_copy": "该关键词暂无候选货源",
        "provider": getattr(container.sourcing_provider, "name", "unknown"),
    }
    if run.status.value == "FAILED":
        payload["err_code"] = run.err_code
        payload["err_layer"] = run.err_layer
    container.audit.record(
        AuditEntry(
            actor=user.username,
            action="sourcing.search",
            object_type="run",
            object_id=run.run_id.value,
            after={"keyword": body.keyword, "count": len(candidates)},
        )
    )
    return payload


@router.get("/sourcing/candidates")
def sourcing_candidates(
    run_id: str | None = Query(default=None),
    container: AppContainer = Depends(get_container),
    user=Depends(get_current_user),
) -> dict[str, Any]:
    run = None
    if run_id:
        run = container.runs.get(RunId.parse(run_id))
        if run is None:
            raise DomainError("E008", f"运行不存在: {run_id}", status_override=404)
    else:
        run = next((item for item in container.runs.recent(50) if item.scene == "S10"), None)
    if run is None:
        return {
            "run_id": None,
            "keyword": "",
            "candidates": [],
            "count": 0,
            "empty_copy": "该关键词暂无候选货源",
            "provider": getattr(container.sourcing_provider, "name", "unknown"),
        }
    items = container.sourcing.by_run(run.run_id)
    return {
        "run_id": run.run_id.value,
        "keyword": str(run.config_snapshot.get("params", {}).get("keyword", "")),
        "candidates": items,
        "count": len(items),
        "empty_copy": "该关键词暂无候选货源",
        "provider": getattr(container.sourcing_provider, "name", "unknown"),
    }


@router.get("/sourcing/candidates/{offer_id}")
def sourcing_candidate(
    offer_id: str,
    container: AppContainer = Depends(get_container),
    user=Depends(get_current_user),
) -> dict[str, Any]:
    candidate = container.sourcing.latest_for_offer(offer_id)
    if candidate is None:
        raise DomainError("E008", f"货源候选不存在: {offer_id}", status_override=404)
    return candidate


@router.get("/sourcing/provider")
def sourcing_provider_status(
    container: AppContainer = Depends(get_container),
    user=Depends(get_current_user),
) -> dict[str, Any]:
    return {
        "mode": container.settings.source_1688_mode,
        "sourcing_provider": getattr(container.sourcing_provider, "name", "unknown"),
        "purchase_provider": getattr(container.purchase_provider, "name", "unknown"),
        "note": "选品可自动；下单只创建 checkout，支付必须由人在 1688/UTP 收银台完成",
    }


@router.get("/purchases")
def list_purchases(
    status: str | None = Query(default=None),
    container: AppContainer = Depends(get_container),
    user=Depends(get_current_user),
) -> dict[str, Any]:
    orders = container.purchases.recent(50)
    items = []
    for order in orders:
        if status and order.status.value != status:
            continue
        plan = container.write_plans.get(order.plan_id)
        items.append(
            {
                **order.to_dict(),
                "task_id": plan.approval_task_id if plan else None,
            }
        )
    return {"items": items, "empty_copy": "暂无采购单", "readonly": True}


@router.post("/purchases/{plan_id}/refresh")
def refresh_purchase(
    plan_id: str,
    container: AppContainer = Depends(get_container),
    user=Depends(get_current_user),
) -> dict[str, Any]:
    order = container.purchases.get(plan_id)
    if order is None:
        raise DomainError("E008", f"采购单不存在: {plan_id}", status_override=404)
    plan = container.write_plans.get(plan_id)
    try:
        result = container.skills.execute(
            "purchase.status",
            {"checkout_id": order.checkout_id},
            scene="S11",
            platform=plan.platform if plan else "demo",
            shop_id=plan.shop_id if plan else "SHOP-0001",
            run_id=plan_id,
        )
    except SkillUnavailable as exc:
        raise DomainError("E008", f"查询 1688 checkout 失败: {exc}") from exc
    data = dict(result.data or {})
    order.status = PurchaseStatus(str(data.get("status", "AWAITING_PAYMENT")))
    order.continue_url = str(data.get("continue_url") or order.continue_url)
    container.purchases.save(order)
    container.audit.record(
        AuditEntry(
            actor=user.username,
            action="purchase.refresh",
            object_type="purchase_order",
            object_id=plan_id,
            after={"status": order.status.value},
        )
    )
    return {
        **order.to_dict(),
        "task_id": plan.approval_task_id if plan else None,
        "note": "支付状态来自 1688/UTP 回读；本系统不代付",
    }
