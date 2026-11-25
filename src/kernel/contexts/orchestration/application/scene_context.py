"""运行上下文：场景模块只能通过这里的端口访问取数、数据中枢、通知与审计。

模块拿不到数据库会话、拿不到凭据，也拿不到 /write 能力——这是"业务模块不越权"的落点。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Mapping

from kernel.contexts.approval.domain.gate_policy import GatePolicyService
from kernel.contexts.integration.application.notification_service import NotificationService
from kernel.contexts.integration.domain.desensitizer import Desensitizer
from kernel.contexts.integration.domain.fetch_strategy import FetchStrategyResolver
from kernel.contexts.metric_data.application.daily_report import DailyReportBuilder
from kernel.contexts.metric_data.domain.metric_definition import MetricCalculator
from kernel.contexts.integration.domain.notification import SubscriptionRepository
from kernel.contexts.metric_data.domain.ports import (
    AdCampaignRepository,
    DwdRepository,
    DwsRepository,
    MetricRepository,
    OdsRepository,
    ReportRepository,
    ReportStorage,
    ReviewTicketRepository,
    SettlementRepository,
    StockRepository,
)
from kernel.contexts.observability.domain.models import AuditEntry, AuditPort, ExceptionPort
from kernel.contexts.orchestration.domain.ports import Clock, RunRepository
from kernel.contexts.orchestration.domain.run import NodeExecution, NodeStatus, Run
from kernel.contracts.extension_points import PlatformAdapterPort
from shared.errors.registry import DomainError
from shared.types.values import Channel, StatWindow


@dataclass
class SceneContext:
    run: Run
    run_repo: RunRepository
    clock: Clock
    config: dict[str, Any]
    fetch: FetchStrategyResolver
    adapters: Mapping[str, PlatformAdapterPort]
    desensitizer: Desensitizer
    ods: OdsRepository
    dwd: DwdRepository
    dws: DwsRepository
    metrics: MetricRepository
    calculator: MetricCalculator
    reports: ReportRepository
    storage: ReportStorage
    report_builder: DailyReportBuilder
    review_tickets: ReviewTicketRepository
    stock: StockRepository
    ads: AdCampaignRepository
    settlements: SettlementRepository
    subscriptions: SubscriptionRepository | None
    notifier: NotificationService
    audit: AuditPort
    exceptions: ExceptionPort
    gate: GatePolicyService
    timezone: str = "Asia/Shanghai"
    datasets: list[str] = field(default_factory=list)
    _timers: dict[str, float] = field(default_factory=dict, repr=False)

    @property
    def window(self) -> StatWindow:
        return self.run.window

    @property
    def platform(self) -> str:
        return self.run.platform

    @property
    def shop_id(self) -> str:
        return self.run.shop_id

    def adapter(self) -> PlatformAdapterPort:
        adapter = self.adapters.get(self.platform)
        if adapter is None:
            raise DomainError("E008", f"未注册平台适配器: {self.platform}")
        return adapter

    # ------------------------------------------------------------------ nodes
    def begin_node(self, node_id: str) -> None:
        self._timers[node_id] = time.perf_counter()
        self._record_node(node_id, NodeStatus.RUNNING)

    def end_node(
        self,
        node_id: str,
        *,
        channel: Channel | None = None,
        payload_digest: str | None = None,
        cost_ms: int | None = None,
    ) -> None:
        elapsed = cost_ms
        if elapsed is None:
            started = self._timers.pop(node_id, None)
            elapsed = int((time.perf_counter() - started) * 1000) if started else 0
        self._record_node(
            node_id,
            NodeStatus.SUCCEEDED,
            cost_ms=elapsed,
            channel=channel,
            payload_digest=payload_digest,
        )

    def fail_node(self, node_id: str, error: DomainError) -> None:
        started = self._timers.pop(node_id, None)
        elapsed = int((time.perf_counter() - started) * 1000) if started else 0
        self._record_node(
            node_id,
            NodeStatus.FAILED,
            cost_ms=elapsed,
            err_code=error.code,
            err_layer=error.layer,
        )

    def skip_node(self, node_id: str, note: str = "") -> None:
        self._record_node(node_id, NodeStatus.SKIPPED)
        self.notifier.send(
            event="EVT-07",
            receiver="ops",
            title=f"{node_id} 跳过",
            body=note or f"{node_id} 在本次运行中被跳过",
            dedupe_key=f"EVT-07:{self.run.run_id.value}:{node_id}",
        )

    def _record_node(
        self,
        node_id: str,
        status: NodeStatus,
        *,
        cost_ms: int = 0,
        channel: Channel | None = None,
        err_code: str | None = None,
        err_layer: str | None = None,
        payload_digest: str | None = None,
    ) -> None:
        self.run.record_node(
            NodeExecution(
                node_id=node_id,
                status=status,
                cost_ms=cost_ms,
                channel=channel,
                err_code=err_code,
                err_layer=err_layer,
                payload_digest=payload_digest,
            )
        )
        self.run_repo.save(self.run)

    # ------------------------------------------------------------------ side channels
    def audit_log(
        self,
        action: str,
        object_type: str,
        object_id: str,
        *,
        actor: str | None = None,
        reason: str | None = None,
        after: dict[str, Any] | None = None,
    ) -> None:
        self.audit.record(
            AuditEntry(
                actor=actor or self.run.requested_by,
                action=action,
                object_type=object_type,
                object_id=object_id,
                reason=reason,
                after=after,
            )
        )

    def receivers(self, event: str, defaults: list[str] | None = None) -> list[str]:
        """订阅人合并：场景默认接收人 + P12 订阅（按事件）。"""
        base = set(defaults or [])
        if self.subscriptions is not None:
            base.update(self.subscriptions.receivers_for(event))
        return sorted(base)

    def notify(
        self,
        *,
        event: str,
        receiver: str,
        title: str,
        body: str,
        dedupe_key: str,
        payload: dict[str, Any] | None = None,
    ) -> bool:
        return self.notifier.send(
            event=event,
            receiver=receiver,
            title=title,
            body=body,
            dedupe_key=dedupe_key,
            payload=payload,
        )
