"""S09 结算对账处理器：订单 − 退款 − 佣金 vs 结算单，差异分级并保留双边凭据。

只读：财务写入属 L3，模块不提供任何回写入口。
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from decimal import Decimal
from typing import Any

from kernel.contexts.integration.domain.models import FetchSpec
from kernel.contexts.metric_data.domain.settlement import (
    SettlementOrder,
    SettlementRecord,
    SettlementReconciler,
)
from kernel.contexts.orchestration.application.scene_context import SceneContext
from kernel.contracts.extension_points import SceneResult
from shared.errors.registry import DomainError
from shared.gate_level import GateLevel
from shared.types.values import Channel


class SettlementReconHandler:
    scene = "S09"
    gate_level = GateLevel.L0_READ_ONLY

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.datasets: list[str] = list(config.get("datasets", ["order", "settlement"]))
        self.reconciler = SettlementReconciler(
            tolerance=Decimal(str(config.get("tolerance", "0.01")))
        )
        self.subscribers: list[str] = list(config.get("subscribers", ["owner"]))

    def run(self, ctx: SceneContext) -> SceneResult:
        ctx.begin_node("T0")
        ctx.end_node("T0")
        channel, records = self._collect(ctx)
        self._normalize(ctx, records)
        orders, settlements = self._split(records)
        diffs = self.reconciler.reconcile(orders, settlements)
        self._route(ctx)
        self._persist(ctx, diffs)
        self._verify(ctx, diffs)
        counts: dict[str, int] = {}
        for diff in diffs:
            counts[diff.diff_type.value] = counts.get(diff.diff_type.value, 0) + 1
        return SceneResult(
            metrics_written=len(diffs),
            gate_level=GateLevel.L0_READ_ONLY,
            details={"diffs": len(diffs), "counts": counts, "channel": channel.value},
        )

    # ------------------------------------------------------------------ T1
    def _collect(self, ctx: SceneContext) -> tuple[Channel, list[Any]]:
        ctx.begin_node("T1")
        records: list[Any] = []
        channel = Channel.BACKEND_EXPORT
        digests: list[str] = []
        try:
            for dataset in self.datasets:
                spec = FetchSpec(
                    platform=ctx.platform,
                    shop_id=ctx.shop_id,
                    dataset=dataset,
                    window=ctx.window,
                    config={"scene": self.scene},
                )
                raw = ctx.fetch.resolve(spec)
                channel = raw.channel
                ctx.ods.save(ctx.run.run_id, raw)
                digests.append(raw.payload_hash)
                records.extend(ctx.desensitizer.mask_records(ctx.adapter().to_canonical(raw)))
        except DomainError as exc:
            ctx.fail_node("T1", exc)
            raise
        ctx.end_node(
            "T1",
            channel=channel,
            payload_digest=hashlib.sha256("|".join(digests).encode()).hexdigest()[:32],
        )
        return channel, records

    # ------------------------------------------------------------------ T2
    def _normalize(self, ctx: SceneContext, records: list[Any]) -> None:
        ctx.begin_node("T2")
        write = ctx.dwd.save_records(ctx.run.run_id, records)
        ctx.end_node("T2", payload_digest=f"records:{write.saved}")

    @staticmethod
    def _split(records: list[Any]) -> tuple[list[SettlementOrder], list[SettlementRecord]]:
        orders: list[SettlementOrder] = []
        settlements: list[SettlementRecord] = []
        for record in records:
            if record.dataset == "order":
                orders.append(
                    SettlementOrder(
                        order_id=str(record.value("order_id", "")),
                        paid_amount=_decimal(record.value("paid_amount")),
                        refund_amount=_decimal(record.value("refund_amount")),
                        sku=str(record.value("sku", "") or ""),
                        ref=str(record.raw_ref or ""),
                    )
                )
            elif record.dataset == "settlement":
                settled_at = None
                if record.value("settlement_date"):
                    try:
                        settled_at = datetime.fromisoformat(
                            str(record.value("settlement_date"))
                        )
                    except ValueError:
                        settled_at = None
                settlements.append(
                    SettlementRecord(
                        order_id=str(record.value("order_id", "")),
                        settlement_no=str(record.value("settlement_no", "")),
                        settlement_amount=_decimal(record.value("settlement_amount")),
                        commission=_decimal(record.value("commission")),
                        settled_at=settled_at,
                        ref=str(record.raw_ref or ""),
                    )
                )
        return orders, settlements

    # ------------------------------------------------------------------ T4
    def _route(self, ctx: SceneContext) -> None:
        ctx.begin_node("T4")
        decision = ctx.gate.decide("S09.report")
        if not decision.allowed:
            error = DomainError("E007", decision.reason)
            ctx.fail_node("T4", error)
            raise error
        ctx.end_node("T4")

    # ------------------------------------------------------------------ T5
    def _persist(self, ctx: SceneContext, diffs: list[Any]) -> None:
        ctx.begin_node("T5")
        ctx.settlements.save(ctx.run.run_id, ctx.platform, ctx.shop_id, diffs)
        ctx.audit_log(
            "settlement.reconcile",
            "run",
            ctx.run.run_id.value,
            after={"diffs": len(diffs)},
        )
        ctx.end_node("T5", payload_digest=f"diffs:{len(diffs)}")

    # ------------------------------------------------------------------ T6
    def _verify(self, ctx: SceneContext, diffs: list[Any]) -> None:
        ctx.begin_node("T6")
        stored = ctx.settlements.by_run(ctx.run.run_id)
        if len(stored) != len(diffs):
            error = DomainError("E006", "对账差异落库条数与计算不一致")
            ctx.fail_node("T6", error)
            raise error
        ctx.end_node("T6", payload_digest=f"verified:{len(diffs)}")


def _decimal(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal(0)
    return Decimal(str(value))
