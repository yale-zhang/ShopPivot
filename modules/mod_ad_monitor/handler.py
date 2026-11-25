"""S04 投放归集处理器：按计划汇总花费/成交/投产比 → 阈值预警 → 建议（不调价）。"""
from __future__ import annotations

import hashlib
from decimal import Decimal
from typing import Any

from kernel.contexts.integration.domain.models import FetchSpec
from kernel.contexts.orchestration.application.scene_context import SceneContext
from kernel.contracts.extension_points import SceneResult
from shared.errors.registry import DomainError
from shared.gate_level import GateLevel
from shared.types.values import Channel


class AdMonitorHandler:
    scene = "S04"
    gate_level = GateLevel.L0_READ_ONLY

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.datasets: list[str] = list(config.get("datasets", ["ad"]))
        self.roi_min = float(config.get("roi_min", 2.0))
        self.watch_min = float(config.get("watch_min", 1.0))
        self.subscribers: list[str] = list(config.get("subscribers", ["owner"]))

    def run(self, ctx: SceneContext) -> SceneResult:
        ctx.begin_node("T0")
        ctx.end_node("T0")
        channel, records = self._collect(ctx)
        self._normalize(ctx, records)
        rows = self._aggregate(ctx, records)
        self._route(ctx)
        self._persist(ctx, rows)
        self._notify(ctx, rows)
        self._verify(ctx, rows)
        return SceneResult(
            metrics_written=len(rows),
            gate_level=GateLevel.L0_READ_ONLY,
            details={"campaigns": len(rows), "alerts": len([r for r in rows if r["alert_level"] != "OK"])},
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

    # ------------------------------------------------------------------ T3
    def _aggregate(self, ctx: SceneContext, records: list[Any]) -> list[dict[str, Any]]:
        ctx.begin_node("T3")
        totals: dict[str, dict[str, Decimal]] = {}
        for record in records:
            if record.dataset != "ad":
                continue
            campaign = str(record.value("campaign", "") or "未命名计划")
            cost = _decimal(record.value("cost"))
            revenue = _decimal(record.value("attributed_revenue"))
            bucket = totals.setdefault(campaign, {"cost": Decimal(0), "revenue": Decimal(0)})
            bucket["cost"] += cost
            bucket["revenue"] += revenue

        rows: list[dict[str, Any]] = []
        for campaign, bucket in sorted(totals.items()):
            cost = bucket["cost"]
            revenue = bucket["revenue"]
            roi = (revenue / cost) if cost > 0 else None
            if roi is None:
                level, suggestion = "WATCH", "无花费，无法计算投产比"
            elif roi < Decimal(str(self.watch_min)):
                level, suggestion = "ALERT", "投产比过低，建议核对归因或暂停该计划（不自动调价）"
            elif roi < Decimal(str(self.roi_min)):
                level, suggestion = "WATCH", "投产比低于目标，建议优化出价/人群（不自动调价）"
            else:
                level, suggestion = "OK", "投产比达标"
            rows.append(
                {
                    "campaign": campaign,
                    "cost": float(cost),
                    "revenue": float(revenue),
                    "roi": float(roi) if roi is not None else None,
                    "alert_level": level,
                    "suggestion": suggestion,
                }
            )
        ctx.end_node("T3", payload_digest=f"campaigns:{len(rows)}")
        return rows

    # ------------------------------------------------------------------ T4
    def _route(self, ctx: SceneContext) -> None:
        ctx.begin_node("T4")
        decision = ctx.gate.decide("S04.report")
        if not decision.allowed:
            error = DomainError("E007", decision.reason)
            ctx.fail_node("T4", error)
            raise error
        ctx.end_node("T4")

    # ------------------------------------------------------------------ T5
    def _persist(self, ctx: SceneContext, rows: list[dict[str, Any]]) -> None:
        ctx.begin_node("T5")
        ctx.ads.save(ctx.run.run_id, ctx.platform, ctx.shop_id, ctx.window.end, rows)
        ctx.audit_log("ad.monitor", "run", ctx.run.run_id.value, after={"campaigns": len(rows)})
        ctx.end_node("T5", payload_digest=f"campaigns:{len(rows)}")

    # ------------------------------------------------------------------ notify
    def _notify(self, ctx: SceneContext, rows: list[dict[str, Any]]) -> None:
        alerts = [row for row in rows if row["alert_level"] in {"ALERT", "WATCH"}]
        if not alerts:
            return
        receivers = ctx.receivers("EVT-02", self.subscribers)
        for row in alerts:
            for receiver in receivers:
                ctx.notify(
                    event="EVT-02",
                    receiver=receiver,
                    title=f"投产比预警 · {row['campaign']}",
                    body=(
                        f"花费 ¥{row['cost']:.2f}、成交 ¥{row['revenue']:.2f}、"
                        f"投产比 {row['roi'] if row['roi'] is not None else '不适用'}，"
                        f"{row['suggestion']}"
                    ),
                    dedupe_key=f"EVT-02:{ctx.run.run_id.value}:{row['campaign']}:{receiver}",
                    payload={"campaign": row["campaign"], "alert_level": row["alert_level"]},
                )

    # ------------------------------------------------------------------ T6
    def _verify(self, ctx: SceneContext, rows: list[dict[str, Any]]) -> None:
        ctx.begin_node("T6")
        stored = ctx.ads.by_run(ctx.run.run_id)
        if len(stored) != len(rows):
            error = DomainError("E006", "投放汇总落库条数与计算不一致")
            ctx.fail_node("T6", error)
            raise error
        ctx.end_node("T6", payload_digest=f"verified:{len(rows)}")


def _decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal(0)
    return Decimal(str(value))
