"""1688 选品与采购处理器。

选品：S10 只读搜索 + 规则评分。
采购：S11 L2 WriteAction；只创建 checkout，支付必须由人在 UTP 卡片/1688 收银台完成。
"""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from kernel.contexts.integration.domain.sourcing import ProviderUnavailable
from kernel.contexts.skill.domain.models import SkillUnavailable
from kernel.contexts.metric_data.domain.purchase import (
    PurchaseItem,
    PurchaseOrder,
    PurchaseStatus,
)
from kernel.contexts.metric_data.domain.sourcing import SourcingScorer
from kernel.contexts.orchestration.application.scene_context import SceneContext
from kernel.contracts.extension_points import ActionResult, ActionPlan, SceneResult, WriteActionRequest
from shared.errors.registry import DomainError
from shared.gate_level import GateLevel


class SourcingHandler:
    scene = "S10"
    gate_level = GateLevel.L0_READ_ONLY

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.provider = config.get("_provider")
        self.default_keyword = str(config.get("default_keyword", "垃圾袋"))
        self.limit = int(config.get("limit", 20))
        self.scorer = SourcingScorer()

    def run(self, ctx: SceneContext) -> SceneResult:
        ctx.begin_node("T0")
        ctx.end_node("T0")
        params = dict(ctx.run.config_snapshot.get("params") or {})
        keyword = str(params.get("keyword") or self.default_keyword).strip()
        filters = list(params.get("filters") or [])
        limit = int(params.get("limit") or self.limit)
        if not keyword:
            error = DomainError("E006", "选品关键词不能为空")
            ctx.fail_node("T1", error)
            raise error
        ctx.begin_node("T1")
        try:
            if ctx.skills is not None:
                output = ctx.skills.execute(
                    "sourcing.search",
                    {"keyword": keyword, "limit": limit, "filters": filters},
                    scene=self.scene,
                    platform=ctx.platform,
                    shop_id=ctx.shop_id,
                    run_id=ctx.run.run_id.value,
                )
                offers = list(output.data or [])
            else:
                if self.provider is None:
                    raise ProviderUnavailable("未配置 1688 选品提供方")
                offers = self.provider.search(keyword, limit=limit, filters=filters)
        except (ProviderUnavailable, SkillUnavailable) as exc:
            error = DomainError("E008", f"1688 选品不可用: {exc}")
            ctx.fail_node("T1", error)
            raise error
        ctx.end_node("T1", payload_digest=f"offers:{len(offers)}")

        ctx.begin_node("T2")
        candidates = self.scorer.score(offers)
        ctx.end_node("T2", payload_digest=f"candidates:{len(candidates)}")

        ctx.begin_node("T3")
        ctx.sourcing.save(ctx.run.run_id, keyword, candidates)
        ctx.audit_log(
            "sourcing.search",
            "run",
            ctx.run.run_id.value,
            after={"keyword": keyword, "candidates": len(candidates)},
        )
        ctx.end_node("T3", payload_digest=f"saved:{len(candidates)}")

        ctx.begin_node("T4")
        decision = ctx.gate.decide("S10.sourcing")
        if not decision.allowed:
            error = DomainError("E007", decision.reason)
            ctx.fail_node("T4", error)
            raise error
        ctx.end_node("T4")

        ctx.begin_node("T6")
        stored = ctx.sourcing.by_run(ctx.run.run_id)
        if len(stored) != len(candidates):
            error = DomainError("E006", "选品候选落库条数与计算不一致")
            ctx.fail_node("T6", error)
            raise error
        ctx.end_node("T6", payload_digest=f"verified:{len(stored)}")
        return SceneResult(
            metrics_written=len(candidates),
            gate_level=GateLevel.L0_READ_ONLY,
            details={
                "keyword": keyword,
                "candidates": len(candidates),
                "top_offer": candidates[0].offer.offer_id if candidates else None,
            },
        )


class PurchaseOrderAction:
    action_code = "S11.purchase_order"

    def __init__(self, config: dict[str, Any]) -> None:
        self.provider = config.get("_purchase_provider")
        self.purchases = config.get("_purchases")
        self.sourcing = config.get("_sourcing")
        self.skills = config.get("_skills")

    # ------------------------------------------------------------------ plan
    def build(self, request: WriteActionRequest) -> ActionPlan:
        if self.sourcing is None:
            raise DomainError("E008", "采购模块缺少选品仓储")
        items: list[PurchaseItem] = []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw in request.rows:
            offer_id = str(raw.get("offer_id", "")).strip()
            if not offer_id:
                raise DomainError("E006", "采购清单缺少 offer_id")
            if offer_id in seen:
                raise DomainError("E006", f"采购清单重复货源: {offer_id}")
            seen.add(offer_id)
            quantity = int(raw.get("quantity") or 0)
            if quantity <= 0:
                raise DomainError("E006", f"采购数量必须大于 0: {offer_id}")
            candidate = self.sourcing.latest_for_offer(offer_id)
            if candidate is None:
                raise DomainError("E004", f"未找到货源候选: {offer_id}，请先执行选品")
            if not candidate["brand_authorized"]:
                raise DomainError("E006", f"品牌未授权货源禁止采购: {offer_id}")
            if quantity < int(candidate["moq"]):
                raise DomainError(
                    "E006",
                    f"{offer_id} 起订量为 {candidate['moq']}，当前 {quantity} 件不满足",
                )
            items.append(
                PurchaseItem(
                    offer_id=offer_id,
                    title=str(candidate["title"]),
                    quantity=quantity,
                    unit_price=Decimal(str(candidate["price"])),
                    post_fee=Decimal(str(candidate["post_fee"])),
                )
            )
            rows.append(
                {
                    "target": offer_id,
                    "field": "purchase",
                    "before": "未下单",
                    "after": f"{quantity} 件",
                    "impact": f"{candidate['title']} · 单价 ¥{candidate['price']}",
                }
            )
        if not items:
            raise DomainError("E006", "采购清单为空")
        total = sum((item.subtotal for item in items), Decimal("0.00")) + sum(
            (item.post_fee for item in items), Decimal("0.00")
        )
        first = items[0]
        return ActionPlan(
            rows=rows,
            before_snapshot={
                "shot": f"offer://1688/{first.offer_id}",
                "items": [item.to_dict() for item in items],
                "total": str(total.quantize(Decimal("0.01"))),
                "provider": getattr(self.provider, "name", "unknown"),
                "buyer_note": request.params.get("buyer_note", ""),
            },
            summary=f"1688 采购单 · {len(items)} 个货源",
            impact_scope=f"采购 {sum(item.quantity for item in items)} 件 · 合计 ¥{total.quantize(Decimal('0.01'))}",
            rollback_plan="不代支付；未支付可在 1688 取消 checkout，已支付需走平台退款流程",
            evidence=[
                {"kind": "offer", "ref": f"https://detail.1688.com/offer/{first.offer_id}.html", "label": "1688 货源页"},
                {"kind": "price", "ref": f"price://{first.offer_id}", "label": "货源报价快照"},
                {"kind": "supplier", "ref": f"supplier://{first.offer_id}", "label": "供应商信息"},
            ],
        )

    # ------------------------------------------------------------------ execute
    def apply(self, plan) -> ActionResult:  # type: ignore[no-untyped-def]
        if self.provider is None or self.purchases is None:
            raise DomainError("E008", "采购提供方未配置")
        items = [
            PurchaseItem(
                offer_id=str(item["offer_id"]),
                title=str(item["title"]),
                quantity=int(item["quantity"]),
                unit_price=Decimal(str(item["unit_price"])),
                post_fee=Decimal(str(item.get("post_fee", "0"))),
                spec_id=str(item.get("spec_id", "")),
            )
            for item in plan.before_snapshot.get("items", [])
        ]
        if self.skills is not None:
            try:
                result = self.skills.execute(
                    "purchase.checkout",
                    {
                        "items": [item.to_dict() for item in items],
                        "buyer_note": str(plan.before_snapshot.get("buyer_note", "")),
                    },
                    scene="S11",
                    platform=plan.platform,
                    shop_id=plan.shop_id,
                    run_id=plan.plan_id,
                )
            except SkillUnavailable as exc:
                raise DomainError("E008", f"1688 采购不可用: {exc}") from exc
            data = dict(result.data or {})
            if not result.ok or not data.get("checkout_id"):
                raise DomainError("E008", f"1688 checkout 创建失败: {result.error_code or result.status}")
            checkout_id = str(data["checkout_id"])
            checkout_status = PurchaseStatus(str(data.get("status", "AWAITING_PAYMENT")))
            continue_url = str(data.get("continue_url", ""))
            total = Decimal(str(data.get("total") or plan.before_snapshot.get("total", "0")))
            details = dict(data.get("details") or {})
            provider_name = "skill:1688-utp-shopping"
        else:
            if self.provider is None:
                raise DomainError("E008", "采购提供方未配置")
            try:
                checkout = self.provider.create_checkout(
                    items, buyer_note=str(plan.before_snapshot.get("buyer_note", ""))
                )
            except ProviderUnavailable as exc:
                raise DomainError("E008", f"1688 采购不可用: {exc}") from exc
            checkout_id = checkout.checkout_id
            checkout_status = checkout.status
            continue_url = checkout.continue_url
            total = checkout.total
            details = checkout.details
            provider_name = str(getattr(self.provider, "name", "unknown"))
        order = PurchaseOrder(
            plan_id=plan.plan_id,
            provider=provider_name,
            items=items,
            total=Decimal(str(plan.before_snapshot.get("total", "0"))) if total is None else total,
            checkout_id=checkout_id,
            status=checkout_status,
            continue_url=continue_url,
            buyer_note=str(plan.before_snapshot.get("buyer_note", "")),
            details=details,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self.purchases.add(order)
        return ActionResult(
            verified=checkout_status is not PurchaseStatus.FAILED,
            applied_rows=[
                {
                    "offer_id": item.offer_id,
                    "quantity": item.quantity,
                    "checkout_id": checkout_id,
                }
                for item in items
            ],
            after_shot=f"checkout://{checkout_id}",
            details={
                "checkout_status": checkout_status.value,
                "continue_url": continue_url,
                "note": "支付需由人在 1688/UTP 收银台完成，本系统不代付",
            },
        )

    def verify(self, plan) -> bool:  # type: ignore[no-untyped-def]
        if self.purchases is None:
            return False
        order = self.purchases.get(plan.plan_id)
        if order is None:
            return False
        if self.skills is not None:
            try:
                result = self.skills.execute(
                    "purchase.status",
                    {"checkout_id": order.checkout_id},
                    scene="S11",
                    platform=plan.platform,
                    shop_id=plan.shop_id,
                    run_id=plan.plan_id,
                )
            except SkillUnavailable:
                return False
            data = dict(result.data or {})
            status = PurchaseStatus(str(data.get("status", "AWAITING_PAYMENT")))
            order.status = status
            order.continue_url = str(data.get("continue_url") or order.continue_url)
            order.updated_at = datetime.now(UTC)
            self.purchases.save(order)
            return status is not PurchaseStatus.FAILED
        if self.provider is None:
            return False
        try:
            checkout = self.provider.get_checkout(order.checkout_id)
        except ProviderUnavailable:
            return False
        order.status = checkout.status
        order.continue_url = checkout.continue_url or order.continue_url
        order.updated_at = datetime.now(UTC)
        self.purchases.save(order)
        return checkout.status is not PurchaseStatus.FAILED

    def compensate(self, plan) -> bool:  # type: ignore[no-untyped-def]
        if self.purchases is None:
            return False
        order = self.purchases.get(plan.plan_id)
        if order is None:
            return True
        if self.skills is not None:
            try:
                result = self.skills.execute(
                    "purchase.cancel",
                    {"checkout_id": order.checkout_id},
                    scene="S11",
                    platform=plan.platform,
                    shop_id=plan.shop_id,
                    run_id=plan.plan_id,
                )
            except SkillUnavailable:
                return False
            cancelled = bool((result.data or {}).get("cancelled"))
        else:
            if self.provider is None:
                return False
            cancelled = self.provider.cancel_checkout(order.checkout_id)
        if cancelled:
            order.status = PurchaseStatus.CANCELLED
            self.purchases.save(order)
        return cancelled
