"""S01 经营日报场景处理器：T1 取数 → T2 标准化 → T3 计算 → T4 路由 → T5 出报 → T6 校验归档。

约束：
- 只读：不调用 /write，不产生 ApprovalTask（S01 恒 L0）；
- 取数走三级降级，第三级不可用即 fail-closed；
- 报表与看板同源（DWS），导出带口径版本 / run_id / 脱敏水印。
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from kernel.contexts.integration.domain.models import FetchSpec
from kernel.contexts.metric_data.domain.ports import RawPayload
from kernel.contexts.metric_data.domain.report import Report
from kernel.contexts.metric_data.infrastructure.excel import render_daily_report
from kernel.contexts.orchestration.application.scene_context import SceneContext
from kernel.contracts.extension_points import SceneResult
from shared.errors.registry import DomainError
from shared.gate_level import GateLevel
from shared.types.values import Channel


class DailyReportHandler:
    scene = "S01"
    gate_level = GateLevel.L0_READ_ONLY

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.datasets: list[str] = list(config.get("datasets", ["order", "traffic"]))
        self.subscribers: list[str] = list(config.get("subscribers", ["owner"]))
        self.thresholds: dict[str, float] = dict(config.get("thresholds", {}))

    def run(self, ctx: SceneContext) -> SceneResult:
        ctx.begin_node("T0")
        ctx.end_node("T0")

        channel = self._fetch(ctx)
        write = self._normalize(ctx)
        metric_count, metric_version = self._compute(ctx, channel)
        self._route(ctx)
        report = self._report(ctx, channel, metric_version)
        self._verify(ctx, report, metric_count, write.saved)
        return SceneResult(
            report_id=report.report_id,
            artifact_ref=report.artifact_ref,
            metrics_written=metric_count,
            gate_level=GateLevel.L0_READ_ONLY,
            details={"stat_rows": metric_count, "dwd_saved": write.saved, "channel": channel.value},
        )

    # ------------------------------------------------------------------ T1
    def _fetch(self, ctx: SceneContext) -> Channel:
        ctx.begin_node("T1")
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
        except DomainError as exc:
            ctx.fail_node("T1", exc)
            raise
        ctx.end_node(
            "T1",
            channel=channel,
            payload_digest=hashlib.sha256("|".join(digests).encode()).hexdigest()[:32],
        )
        return channel

    # ------------------------------------------------------------------ T2
    def _normalize(self, ctx: SceneContext) -> Any:
        ctx.begin_node("T2")
        payloads = ctx.ods.by_run(ctx.run.run_id)
        records = []
        try:
            for item in payloads:
                raw = RawPayload(
                    platform=item["platform"],
                    shop_id=item["shop_id"],
                    dataset=item["dataset"],
                    channel=Channel(item["channel"]),
                    records=item["payload"].get("records", []),
                    payload_hash=item["payload_hash"],
                    storage_ref=item["storage_ref"],
                    meta=item["payload"].get("meta", {}),
                )
                records.extend(ctx.desensitizer.mask_records(ctx.adapter().to_canonical(raw)))
            write = ctx.dwd.save_records(ctx.run.run_id, records)
        except DomainError as exc:
            ctx.fail_node("T2", exc)
            raise
        ctx.end_node(
            "T2",
            payload_digest=hashlib.sha256(
                json.dumps(write.datasets, sort_keys=True, default=str).encode()
            ).hexdigest()[:32],
        )
        return write

    # ------------------------------------------------------------------ T3
    def _compute(self, ctx: SceneContext, channel: Channel) -> tuple[int, str]:
        ctx.begin_node("T3")
        try:
            definitions = ctx.metrics.definitions(ctx.platform)
            if not definitions:
                raise DomainError("E008", "没有任何生效口径卡，无法计算指标")
            facts_list = ctx.dwd.facts(ctx.platform, ctx.shop_id, ctx.window)
            total = 0
            for day in facts_list:
                values = ctx.calculator.compute(definitions, day.facts, day.missing_reasons)
                ctx.dws.save(
                    ctx.run.run_id,
                    ctx.platform,
                    ctx.shop_id,
                    day.stat_date,
                    values,
                    channel,
                )
                total += len(values)
        except DomainError as exc:
            ctx.fail_node("T3", exc)
            raise
        versions = sorted({d.version for d in definitions})
        metric_version = f"v{versions[0]}" if len(versions) == 1 else "mixed"
        ctx.end_node("T3", payload_digest=f"metrics:{total}")
        return total, metric_version

    # ------------------------------------------------------------------ T4
    def _route(self, ctx: SceneContext) -> None:
        ctx.begin_node("T4")
        decision = ctx.gate.decide("S01.report")
        if not decision.allowed:
            error = DomainError("E007", decision.reason)
            ctx.fail_node("T4", error)
            raise error
        if decision.gate_level is GateLevel.L2_MANUAL_APPROVAL:
            error = DomainError("E007", "S01 不应进入 L2；请检查 GateRule 配置")
            ctx.fail_node("T4", error)
            raise error
        ctx.end_node("T4")

    # ------------------------------------------------------------------ T5
    def _report(self, ctx: SceneContext, channel: Channel, metric_version: str) -> Report:
        ctx.begin_node("T5")
        try:
            view = ctx.report_builder.build(ctx.run, channel)
            view.metric_version = metric_version
            report = Report.build(
                run_id=ctx.run.run_id,
                platform=ctx.platform,
                shop_id=ctx.shop_id,
                window=ctx.window,
                metric_version=metric_version,
                channel=channel,
            )
            view.watermark = report.watermark
            report.artifact_ref = ctx.storage.put_bytes(
                f"reports/{report.report_id}.xlsx",
                render_daily_report(view),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            ctx.reports.add(report)
            for receiver in ctx.receivers("EVT-01", self.subscribers):
                ctx.notify(
                    event="EVT-01",
                    receiver=receiver,
                    title=f"经营日报 {ctx.window.label}",
                    body=(
                        f"{ctx.platform}/{ctx.shop_id} 日报已生成，口径版本 {metric_version}，"
                        f"run_id {ctx.run.run_id.value}"
                    ),
                    dedupe_key=f"EVT-01:{ctx.run.run_id.value}:{receiver}",
                    payload={
                        "report_id": report.report_id,
                        "artifact_ref": report.artifact_ref,
                        "watermark": report.watermark,
                    },
                )
        except DomainError as exc:
            ctx.fail_node("T5", exc)
            raise
        ctx.end_node("T5", payload_digest=report.report_id)
        return report

    # ------------------------------------------------------------------ T6
    def _verify(
        self, ctx: SceneContext, report: Report, metric_count: int, dwd_saved: int
    ) -> None:
        ctx.begin_node("T6")
        rows = ctx.dws.by_run(ctx.run.run_id)
        if metric_count != len(rows):
            error = DomainError(
                "E006",
                f"DWS 落库条数与计算条数不一致: {metric_count} != {len(rows)}",
            )
            ctx.fail_node("T6", error)
            raise error
        stored = ctx.reports.get(report.report_id)
        if stored is None or not ctx.storage.exists(report.artifact_ref):
            error = DomainError("E008", "报表产物缺失，归档失败")
            ctx.fail_node("T6", error)
            raise error
        ctx.audit_log(
            "report.generate",
            "report",
            report.report_id,
            after={
                "run_id": ctx.run.run_id.value,
                "metric_version": report.metric_version,
                "artifact_ref": report.artifact_ref,
                "dwd_saved": dwd_saved,
            },
        )
        ctx.end_node("T6", payload_digest=report.artifact_ref)
