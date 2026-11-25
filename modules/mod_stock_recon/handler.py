"""S07 库存对账处理器：三方对齐 → 差异分级 → 补货建议。

只输出建议清单，不自动下单；快照时间各自保留，不强行合并。
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from kernel.contexts.integration.domain.models import FetchSpec
from kernel.contexts.metric_data.domain.stock import (
    StockReconciler,
    StockSnapshot,
)
from kernel.contexts.orchestration.application.scene_context import SceneContext
from kernel.contracts.extension_points import SceneResult
from shared.errors.registry import DomainError
from shared.gate_level import GateLevel
from shared.types.values import Channel


class StockReconHandler:
    scene = "S07"
    gate_level = GateLevel.L1_LOW_RISK

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.datasets: list[str] = list(
            config.get("datasets", ["inventory", "erp_inventory", "wms_inventory"])
        )
        self.reconciler = StockReconciler(
            tolerance=int(config.get("tolerance", 5)),
            slow_threshold=int(config.get("slow_threshold", 100)),
            safety_stock=int(config.get("safety_stock", 20)),
        )
        self.subscribers: list[str] = list(config.get("subscribers", ["owner"]))

    def run(self, ctx: SceneContext) -> SceneResult:
        ctx.begin_node("T0")
        ctx.end_node("T0")
        channel, records_by_dataset = self._collect(ctx)
        self._normalize(ctx, records_by_dataset)
        diffs, suggestions, counts = self._reconcile(ctx, records_by_dataset)
        self._route(ctx)
        self._persist(ctx, diffs, suggestions)
        self._verify(ctx, diffs, suggestions, counts)
        return SceneResult(
            report_id=None,
            metrics_written=len(diffs),
            gate_level=GateLevel.L1_LOW_RISK,
            details={
                "diffs": len(diffs),
                "suggestions": len(suggestions),
                "counts": counts,
                "channel": channel.value,
            },
        )

    # ------------------------------------------------------------------ T1
    def _collect(self, ctx: SceneContext) -> tuple[Channel, dict[str, list[Any]]]:
        ctx.begin_node("T1")
        records: dict[str, list[Any]] = {}
        digests: list[str] = []
        channel = Channel.BACKEND_EXPORT
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
                records[dataset] = list(ctx.adapter().to_canonical(raw))
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
    def _normalize(self, ctx: SceneContext, records_by_dataset: dict[str, list[Any]]) -> None:
        ctx.begin_node("T2")
        try:
            all_records = [record for records in records_by_dataset.values() for record in records]
            write = ctx.dwd.save_records(ctx.run.run_id, all_records)
        except DomainError as exc:
            ctx.fail_node("T2", exc)
            raise
        ctx.end_node("T2", payload_digest=f"records:{write.saved}")

    # ------------------------------------------------------------------ T3
    def _reconcile(
        self, ctx: SceneContext, records_by_dataset: dict[str, list[Any]]
    ) -> tuple[list[Any], list[Any], dict[str, int]]:
        ctx.begin_node("T3")
        tz = ZoneInfo(ctx.timezone)
        platform = self._snapshots(records_by_dataset.get("inventory", []), "platform", tz)
        erp = self._snapshots(records_by_dataset.get("erp_inventory", []), "erp", tz)
        wms = self._snapshots(records_by_dataset.get("wms_inventory", []), "wms", tz)
        result = self.reconciler.reconcile(platform, erp, wms)
        ctx.end_node("T3", payload_digest=f"diffs:{len(result.diffs)}")
        return result.diffs, result.suggestions, result.counts

    @staticmethod
    def _snapshots(records: list[Any], source: str, tz: ZoneInfo) -> dict[str, StockSnapshot]:
        snapshots: dict[str, StockSnapshot] = {}
        for record in records:
            sku = str(record.value("sku", "") or record.business_key)
            available_raw = record.value("available")
            available = int(available_raw) if available_raw is not None else None
            snapshot_at = _parse_dt(record.value("snapshot_at"), tz)
            snapshots[sku] = StockSnapshot(
                sku=sku, available=available, snapshot_at=snapshot_at, source=source
            )
        return snapshots

    # ------------------------------------------------------------------ T4
    def _route(self, ctx: SceneContext) -> None:
        ctx.begin_node("T4")
        decision = ctx.gate.decide("S07.suggestion")
        if not decision.allowed:
            error = DomainError("E007", decision.reason)
            ctx.fail_node("T4", error)
            raise error
        if decision.gate_level is GateLevel.L2_MANUAL_APPROVAL:
            error = DomainError("E007", "S07 补货建议不应进入 L2；请检查 GateRule 配置")
            ctx.fail_node("T4", error)
            raise error
        ctx.end_node("T4")

    # ------------------------------------------------------------------ T5
    def _persist(self, ctx: SceneContext, diffs: list[Any], suggestions: list[Any]) -> None:
        ctx.begin_node("T5")
        try:
            ctx.stock.save(
                ctx.run.run_id, ctx.platform, ctx.shop_id, diffs, suggestions
            )
            actionable = [diff for diff in diffs if diff.diff_type.value != "CONSISTENT"]
            if actionable:
                counts = {}
                for diff in actionable:
                    counts[diff.diff_type.label] = counts.get(diff.diff_type.label, 0) + 1
                for receiver in ctx.receivers("EVT-04", self.subscribers):
                    ctx.notify(
                        event="EVT-04",
                        receiver=receiver,
                        title=f"库存差异 {len(actionable)} 条",
                        body=(
                            f"{ctx.platform}/{ctx.shop_id} 存在 {counts}，"
                            f"补货建议 {len(suggestions)} 条（只出建议，不自动下单）"
                        ),
                        dedupe_key=f"EVT-04:{ctx.run.run_id.value}:{receiver}",
                        payload={"run_id": ctx.run.run_id.value, "counts": counts},
                    )
        except DomainError as exc:
            ctx.fail_node("T5", exc)
            raise
        ctx.audit_log(
            "stock.reconcile",
            "run",
            ctx.run.run_id.value,
            after={"diffs": len(diffs), "suggestions": len(suggestions)},
        )
        ctx.end_node("T5", payload_digest=f"diffs:{len(diffs)}")

    # ------------------------------------------------------------------ T6
    def _verify(
        self, ctx: SceneContext, diffs: list[Any], suggestions: list[Any], counts: dict[str, int]
    ) -> None:
        ctx.begin_node("T6")
        stored = ctx.stock.by_run(ctx.run.run_id)
        if len(stored["diffs"]) != len(diffs) or len(stored["suggestions"]) != len(suggestions):
            error = DomainError("E006", "库存对账落库条数与计算结果不一致")
            ctx.fail_node("T6", error)
            raise error
        ctx.end_node("T6", payload_digest=f"verified:{len(diffs)}")


def _parse_dt(value: Any, tz: ZoneInfo) -> datetime | None:
    if value is None or value == "":
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=tz)
    return parsed
