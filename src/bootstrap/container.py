"""应用容器：装配 Kernel 资产、模块、适配器与用例。

手工 DI（不引入框架）：构造顺序显式、可测试、可在 CLI / API / Celery 三处复用。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import select

from bootstrap.settings import Settings, get_settings
from kernel.contexts.approval.domain.gate_policy import GatePolicyService
from kernel.contexts.approval.application.write_flow import WriteFlowService
from kernel.contexts.approval.infrastructure.repositories import (
    SqlApprovalTaskRepository,
    SqlChangeOrderRepository,
    SqlWriteExecutionRepository,
    SqlWritePlanRepository,
    SqlWriteTokenRepository,
)
from kernel.contexts.execution.infrastructure.repositories import SqlWorkerRepository
from kernel.contexts.identity.infrastructure.repositories import (
    SqlAccountRepository,
    SqlApiTokenRepository,
)
from kernel.contexts.integration.application.notification_service import (
    ConsoleNotificationChannel,
    NotificationService,
)
from kernel.contexts.integration.domain.desensitizer import Desensitizer
from kernel.contexts.integration.domain.fetch_strategy import FetchStrategyResolver
from kernel.contexts.integration.infrastructure.local_storage import LocalReportStorage
from kernel.contexts.integration.infrastructure.repositories import (
    SqlNotificationLogRepository,
    SqlSubscriptionRepository,
)
from kernel.contexts.metric_data.application.daily_report import DailyReportBuilder
from kernel.contexts.metric_data.domain.metric_definition import MetricCalculator
from kernel.contexts.metric_data.application.release_gate import MetricReleaseService
from kernel.contexts.metric_data.infrastructure.probe import SqlProbeRunner
from kernel.contexts.metric_data.infrastructure.repositories import (
    SqlAdCampaignRepository,
    SqlDwdRepository,
    SqlDwsRepository,
    SqlMetricReleaseRepository,
    SqlMetricRepository,
    SqlOdsRepository,
    SqlReportRepository,
    SqlReviewTicketRepository,
    SqlSettlementRepository,
    SqlStockRepository,
)
from kernel.contexts.observability.infrastructure.repositories import (
    SqlAuditRepository,
    SqlDeadLetterRepository,
    SqlExceptionRepository,
    SqlN8nCommandLogRepository,
)
from kernel.contexts.orchestration.application.run_pipeline import RunPipelineUseCase
from kernel.contexts.orchestration.application.scene_context import SceneContext
from kernel.contexts.orchestration.application.start_run import (
    SnapshotBuilder,
    StartRunCommand,
    StartRunUseCase,
)
from kernel.contexts.orchestration.domain.ports import Clock, SystemClock
from kernel.contexts.orchestration.domain.run import Run
from kernel.contexts.orchestration.infrastructure.repositories import (
    OutboxPublisher,
    SqlIdempotencyStore,
    SqlRunRepository,
)
from kernel.contracts.extension_points import PlatformAdapterPort, WriteActionHandler
from kernel.module_loader import ModuleLoader, ModuleStartupReport
from kernel.persistence.base import Database
from kernel.persistence.tables import ModuleStateRow
from kernel.registry import ExtensionPointRegistry
from kernel.runtime.factories import import_object
from kernel.runtime.module_services import RuntimeModuleServices


class RuntimeSnapshotBuilder(SnapshotBuilder):
    def __init__(
        self,
        metrics: SqlMetricRepository,
        scene_configs: dict[str, dict[str, Any]],
        settings: Settings,
    ) -> None:
        self.metrics = metrics
        self.scene_configs = scene_configs
        self.settings = settings

    def build(self, *, platform: str, shop_id: str, scene: str) -> dict[str, Any]:
        definitions = self.metrics.definitions(platform)
        config = self.scene_configs.get(scene, {})
        return {
            "platform": platform,
            "shop_id": shop_id,
            "metric_versions": [
                {"code": d.metric_code, "version": d.version, "additivity": d.additivity.value}
                for d in definitions
            ],
            "thresholds": config.get("thresholds", {}),
            "subscribers": config.get("subscribers", ["owner"]),
            "datasets": config.get("datasets", []),
            "platform_gate_max": self.settings.platform_gate_max.value,
            "timezone": self.settings.timezone,
        }


@dataclass
class AppContainer:
    settings: Settings
    database: Database
    registry: ExtensionPointRegistry
    startup_report: ModuleStartupReport | None
    modules_dirs: list[Path]

    runs: SqlRunRepository
    idempotency: SqlIdempotencyStore
    outbox: OutboxPublisher
    approvals: SqlApprovalTaskRepository
    change_orders: SqlChangeOrderRepository
    write_plans: SqlWritePlanRepository
    write_executions: SqlWriteExecutionRepository
    write_tokens: SqlWriteTokenRepository
    write_handlers: dict[str, WriteActionHandler]
    write_flow: WriteFlowService
    metrics: SqlMetricRepository
    ods: SqlOdsRepository
    dwd: SqlDwdRepository
    dws: SqlDwsRepository
    reports: SqlReportRepository
    review_tickets: SqlReviewTicketRepository
    stock: SqlStockRepository
    ads: SqlAdCampaignRepository
    settlements: SqlSettlementRepository
    subscriptions: SqlSubscriptionRepository
    releases: SqlMetricReleaseRepository
    probes: SqlProbeRunner
    release_gate: MetricReleaseService
    storage: LocalReportStorage
    notification_log: SqlNotificationLogRepository
    notifier: NotificationService
    audit: SqlAuditRepository
    exceptions: SqlExceptionRepository
    dead_letters: SqlDeadLetterRepository
    n8n_commands: SqlN8nCommandLogRepository
    workers: SqlWorkerRepository
    accounts: SqlAccountRepository
    api_tokens: SqlApiTokenRepository
    gate: GatePolicyService
    adapters: dict[str, PlatformAdapterPort]
    scene_configs: dict[str, dict[str, Any]]
    calculator: MetricCalculator
    report_builder: DailyReportBuilder
    start_run: StartRunUseCase
    pipeline: RunPipelineUseCase
    clock: Clock = field(default_factory=SystemClock)
    module_services: RuntimeModuleServices | None = None

    def new_context(self, run: Run, config: dict[str, Any]) -> SceneContext:
        return SceneContext(
            run=run,
            run_repo=self.runs,
            clock=self.clock,
            config=config,
            fetch=FetchStrategyResolver(self.adapters, allow_gui=False),
            adapters=self.adapters,
            desensitizer=Desensitizer(),
            ods=self.ods,
            dwd=self.dwd,
            dws=self.dws,
            metrics=self.metrics,
            calculator=self.calculator,
            reports=self.reports,
            storage=self.storage,
            report_builder=self.report_builder,
            review_tickets=self.review_tickets,
            stock=self.stock,
            ads=self.ads,
            settlements=self.settlements,
            subscriptions=self.subscriptions,
            notifier=self.notifier,
            audit=self.audit,
            exceptions=self.exceptions,
            gate=self.gate,
            timezone=self.settings.timezone,
            datasets=list(config.get("datasets", [])),
        )


def build_container(
    settings: Settings | None = None,
    *,
    database: Database | None = None,
    modules_dirs: list[Path] | None = None,
    load_modules: bool = True,
) -> AppContainer:
    settings = settings or get_settings()
    settings.ensure_dirs()
    database = database or Database(settings.database_url)
    database.create_all()

    modules_dirs = modules_dirs or [settings.modules_dir]

    runs = SqlRunRepository(database)
    idempotency = SqlIdempotencyStore(database)
    outbox = OutboxPublisher(database)
    approvals = SqlApprovalTaskRepository(database)
    change_orders = SqlChangeOrderRepository(database)
    write_plans = SqlWritePlanRepository(database)
    write_executions = SqlWriteExecutionRepository(database)
    write_tokens = SqlWriteTokenRepository(database)
    metrics = SqlMetricRepository(database)
    ods = SqlOdsRepository(database)
    dwd = SqlDwdRepository(database)
    dws = SqlDwsRepository(database)
    reports = SqlReportRepository(database)
    review_tickets = SqlReviewTicketRepository(database)
    stock = SqlStockRepository(database)
    ads = SqlAdCampaignRepository(database)
    settlements = SqlSettlementRepository(database)
    subscriptions = SqlSubscriptionRepository(database)
    releases = SqlMetricReleaseRepository(database)
    probes = SqlProbeRunner(database)
    release_gate = MetricReleaseService(probes)
    storage = LocalReportStorage(settings.storage_dir)
    notification_log = SqlNotificationLogRepository(database)
    notifier = NotificationService(
        notification_log, {"CONSOLE": ConsoleNotificationChannel()}
    )
    audit = SqlAuditRepository(database)
    exceptions = SqlExceptionRepository(database)
    dead_letters = SqlDeadLetterRepository(database)
    n8n_commands = SqlN8nCommandLogRepository(database)
    workers = SqlWorkerRepository(database)
    accounts = SqlAccountRepository(database)
    api_tokens = SqlApiTokenRepository(database)

    module_services = RuntimeModuleServices(database, metrics, modules_dirs)
    with database.session() as session:
        disabled = [
            row.name
            for row in session.execute(
                select(ModuleStateRow).where(ModuleStateRow.enabled.is_(False))
            ).scalars().all()
        ]

    registry = ExtensionPointRegistry()
    startup_report: ModuleStartupReport | None = None
    if load_modules:
        loader = ModuleLoader(
            modules_dirs,
            registry=registry,
            kernel_api="1.0",
            platform_gate_max=settings.platform_gate_max,
            credential_scopes=settings.credential_scopes,
            disabled_modules=disabled,
            services=module_services,
        )
        startup_report = loader.run()

    gate = GatePolicyService(
        module_services.gate_rules,
        platform_ceiling=settings.platform_gate_max,
    )

    adapters: dict[str, PlatformAdapterPort] = {}
    for contribution in registry.by_kind("PlatformAdapter"):
        factory = contribution.config.get("factory")
        if not factory:
            continue
        config = dict(contribution.config)
        config["_module_dir"] = str(Path(modules_dirs[0]) / contribution.module)
        config["_export_dir"] = str(settings.export_dir)
        adapter_cls = import_object(factory)
        adapter = adapter_cls(config)
        platform = str(config.get("platform") or contribution.id)
        adapters[platform] = adapter

    if settings.platform_source and settings.platform_source not in adapters:
        # 显式失败：数据来源没有对应适配器，绝不静默回退
        raise RuntimeError(
            f"平台数据来源 {settings.platform_source!r} 没有可用适配器；"
            f"已注册: {sorted(adapters)}"
        )

    scene_configs: dict[str, dict[str, Any]] = {}
    for contribution in registry.by_kind("ScenePackage"):
        scene = str(contribution.config.get("scene", contribution.id))
        config = dict(contribution.config)
        config["_module_dir"] = str(Path(modules_dirs[0]) / contribution.module)
        scene_configs[scene] = config

    write_handlers: dict[str, WriteActionHandler] = {}
    state_dir = settings.storage_dir / "platform_state"
    state_dir.mkdir(parents=True, exist_ok=True)
    for contribution in registry.by_kind("WriteAction"):
        factory = contribution.config.get("factory")
        if not factory:
            continue
        config = dict(contribution.config)
        config["_state_dir"] = str(state_dir)
        config["_module_dir"] = str(Path(modules_dirs[0]) / contribution.module)
        handler = import_object(factory)(config)
        write_handlers[handler.action_code] = handler

    calculator = MetricCalculator()
    report_builder = DailyReportBuilder(metrics, dws)
    snapshots = RuntimeSnapshotBuilder(metrics, scene_configs, settings)
    clock = SystemClock()
    start_run = StartRunUseCase(
        runs,
        idempotency,
        snapshots,
        outbox,
        clock,
        gate_level_max=settings.platform_gate_max,
    )
    pipeline = RunPipelineUseCase(
        start_run,
        runs,
        registry,
        lambda run, config: container.new_context(run, config),
        outbox,
        clock,
        exceptions,
        dead_letters,
        notifier,
        gate=gate,
    )
    container = AppContainer(
        settings=settings,
        database=database,
        registry=registry,
        startup_report=startup_report,
        modules_dirs=modules_dirs,
        runs=runs,
        idempotency=idempotency,
        outbox=outbox,
        approvals=approvals,
        change_orders=change_orders,
        write_plans=write_plans,
        write_executions=write_executions,
        write_tokens=write_tokens,
        write_handlers=write_handlers,
        write_flow=WriteFlowService(
            plans=write_plans,
            executions=write_executions,
            tokens=write_tokens,
            approvals=approvals,
            handlers=write_handlers,
            gate=gate,
            clock=clock,
            notifier=notifier,
        ),
        metrics=metrics,
        ods=ods,
        dwd=dwd,
        dws=dws,
        reports=reports,
        review_tickets=review_tickets,
        stock=stock,
        ads=ads,
        settlements=settlements,
        subscriptions=subscriptions,
        releases=releases,
        probes=probes,
        release_gate=release_gate,
        storage=storage,
        notification_log=notification_log,
        notifier=notifier,
        audit=audit,
        exceptions=exceptions,
        dead_letters=dead_letters,
        n8n_commands=n8n_commands,
        workers=workers,
        accounts=accounts,
        api_tokens=api_tokens,
        gate=gate,
        adapters=adapters,
        scene_configs=scene_configs,
        calculator=calculator,
        report_builder=report_builder,
        start_run=start_run,
        pipeline=pipeline,
        clock=clock,
        module_services=module_services,
    )
    return container


def run_scene(
    container: AppContainer,
    scene: str,
    *,
    day: str | None = None,
    requested_by: str = "system",
    trigger_type: str = "MANUAL",
):
    """CLI / Celery / API 共用的场景触发入口（S01/S05/S07…）。"""
    from datetime import date

    settings = container.settings
    platform = settings.platform_source or settings.platform
    shop_id = settings.shop_id
    target = date.fromisoformat(day) if day else date.today()
    config = container.scene_configs.get(scene, {})
    app_id = str(config.get("app_id") or f"app_{platform}_{scene.lower()}")
    idempotency_key = f"{scene.lower()}:{platform}:{shop_id}:{target.isoformat()}"
    command = StartRunCommand(
        app_id=app_id,
        scene=scene,
        platform=platform,
        shop_id=shop_id,
        window_start=target,
        window_end=target,
        trigger_type=trigger_type,
        requested_by=requested_by,
        idempotency_key=idempotency_key,
    )
    return container.pipeline(command)


def run_daily(
    container: AppContainer,
    *,
    day: str | None = None,
    requested_by: str = "system",
    trigger_type: str = "MANUAL",
):
    return run_scene(
        container,
        "S01",
        day=day,
        requested_by=requested_by,
        trigger_type=trigger_type,
    )
