"""S05 评价巡检处理器：只读采集 → 负向识别 → 去重工单 → 通知。

约束：
- 同一评价（platform + review_id）只生成一条工单；
- 回复话术由人写，模块只生成待办与证据引用；
- 工单创建属 L1 内部记录，平台经营数据零写入。
"""
from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from typing import Any
from zoneinfo import ZoneInfo

from kernel.contexts.integration.domain.models import FetchSpec
from kernel.contexts.metric_data.domain.review_ticket import (
    ReviewRule,
    ReviewTicket,
    Severity,
)
from kernel.contexts.orchestration.application.scene_context import SceneContext
from kernel.contracts.extension_points import SceneResult
from shared.errors.registry import DomainError
from shared.gate_level import GateLevel
from shared.types.values import Channel


class ReviewPatrolHandler:
    scene = "S05"
    gate_level = GateLevel.L1_LOW_RISK

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.datasets: list[str] = list(config.get("datasets", ["review"]))
        rules = dict(config.get("rules", {}))
        self.rule = ReviewRule(
            rating_threshold=int(rules.get("rating_threshold", 3)),
            high_severity_max=int(rules.get("high_severity_max", 2)),
            keywords=tuple(rules.get("keywords", ())),
        )
        self.sla_hours = int(config.get("sla_hours", 24))
        self.subscribers: list[str] = list(config.get("subscribers", ["editor"]))

    def run(self, ctx: SceneContext) -> SceneResult:
        ctx.begin_node("T0")
        ctx.end_node("T0")
        channel, records = self._collect(ctx)
        self._normalize(ctx, records)
        tickets = self._analyze(ctx, records)
        self._route(ctx)
        created = self._persist(ctx, tickets)
        self._verify(ctx, created)
        return SceneResult(
            report_id=None,
            metrics_written=created,
            gate_level=GateLevel.L1_LOW_RISK,
            details={"tickets_created": created, "reviews": len(records), "channel": channel.value},
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
        try:
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

    # ------------------------------------------------------------------ T3
    def _analyze(self, ctx: SceneContext, records: list[Any]) -> list[ReviewTicket]:
        ctx.begin_node("T3")
        now = ctx.clock.now()
        tickets: list[ReviewTicket] = []
        for record in records:
            review_id = str(record.value("review_id", "") or record.business_key)
            rating = int(record.value("rating", 5) or 5)
            content = str(record.value("content", "") or "")
            hit_rule = self.rule.match(rating, content)
            if hit_rule is None:
                continue
            if ctx.review_tickets.exists(ctx.platform, review_id):
                continue
            severity = (
                Severity.HIGH if rating <= self.rule.high_severity_max else Severity.MEDIUM
            )
            tickets.append(
                ReviewTicket.create(
                    run_id=ctx.run.run_id.value,
                    platform=ctx.platform,
                    shop_id=ctx.shop_id,
                    review_id=review_id,
                    sku=str(record.value("sku", "") or ""),
                    rating=rating,
                    dsr=float(record.value("dsr")) if record.value("dsr") is not None else None,
                    content_masked=str(ctx.desensitizer.display("review_text", content)),
                    hit_rule=hit_rule,
                    severity=severity,
                    sla_due_at=now + timedelta(hours=self.sla_hours),
                    evidence_ref=f"ods://{ctx.run.run_id.value}",
                )
            )
        ctx.end_node("T3", payload_digest=f"tickets:{len(tickets)}")
        return tickets

    # ------------------------------------------------------------------ T4
    def _route(self, ctx: SceneContext) -> None:
        ctx.begin_node("T4")
        decision = ctx.gate.decide("S05.ticket")
        if not decision.allowed:
            error = DomainError("E007", decision.reason)
            ctx.fail_node("T4", error)
            raise error
        if decision.gate_level is GateLevel.L2_MANUAL_APPROVAL:
            error = DomainError("E007", "S05 工单不应进入 L2；请检查 GateRule 配置")
            ctx.fail_node("T4", error)
            raise error
        ctx.end_node("T4")

    # ------------------------------------------------------------------ T5
    def _persist(self, ctx: SceneContext, tickets: list[ReviewTicket]) -> int:
        ctx.begin_node("T5")
        try:
            for ticket in tickets:
                ctx.review_tickets.add(ticket)
                for receiver in ctx.receivers("EVT-03", self.subscribers):
                    ctx.notify(
                        event="EVT-03",
                        receiver=receiver,
                        title=f"差评工单 {ticket.severity.value} · {ticket.sku or ticket.review_id}",
                        body=(
                            f"{ctx.platform}/{ctx.shop_id} 评价 {ticket.review_id} 命中 "
                            f"{ticket.hit_rule}，须在 {ticket.sla_due_at.astimezone(ZoneInfo(ctx.timezone)).strftime('%m-%d %H:%M')} 前处理"
                        ),
                        dedupe_key=f"EVT-03:{ticket.review_id}:{receiver}",
                        payload={
                            "ticket_id": ticket.ticket_id,
                            "review_id": ticket.review_id,
                            "severity": ticket.severity.value,
                        },
                    )
        except DomainError as exc:
            ctx.fail_node("T5", exc)
            raise
        ctx.audit_log(
            "review.patrol",
            "run",
            ctx.run.run_id.value,
            after={"tickets_created": len(tickets)},
        )
        ctx.end_node("T5", payload_digest=f"tickets:{len(tickets)}")
        return len(tickets)

    # ------------------------------------------------------------------ T6
    def _verify(self, ctx: SceneContext, created: int) -> None:
        ctx.begin_node("T6")
        if created < 0:
            error = DomainError("E006", "工单数量异常")
            ctx.fail_node("T6", error)
            raise error
        ctx.end_node("T6", payload_digest=f"tickets:{created}")
