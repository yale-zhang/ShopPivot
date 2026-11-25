"""运行主链用例：T0 触发 → 场景处理 → 成功/失败收口（T6）。

失败一律带 E001~E008 与 err_layer，并写 ExceptionRecord；
run 的状态机与不变量在聚合内，用例只负责编排与持久化。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from kernel.contexts.approval.domain.gate_policy import GatePolicyService
from kernel.contexts.integration.application.notification_service import NotificationService
from kernel.contexts.observability.domain.models import DeadLetterPort, ExceptionPort
from kernel.contexts.orchestration.application.scene_context import SceneContext
from kernel.contexts.orchestration.application.start_run import StartRunCommand, StartRunUseCase
from kernel.contexts.orchestration.domain.ports import Clock, EventPublisher, RunRepository
from kernel.contexts.orchestration.domain.run import Run, RunStatus
from kernel.contracts.extension_points import ScenePackageHandler, SceneResult
from kernel.registry import ExtensionPointRegistry
from kernel.runtime.factories import import_object
from shared.errors.registry import DomainError


@dataclass
class RunPipelineResult:
    run: Run
    scene_result: SceneResult | None = None
    deduplicated: bool = False


class RunPipelineUseCase:
    def __init__(
        self,
        start_run: StartRunUseCase,
        repo: RunRepository,
        registry: ExtensionPointRegistry,
        context_factory: Callable[[Run, dict[str, Any]], SceneContext],
        publisher: EventPublisher,
        clock: Clock,
        exceptions: ExceptionPort,
        dead_letters: DeadLetterPort,
        notifier: NotificationService,
        *,
        gate: GatePolicyService,
    ) -> None:
        self.start_run = start_run
        self.repo = repo
        self.registry = registry
        self.context_factory = context_factory
        self.publisher = publisher
        self.clock = clock
        self.exceptions = exceptions
        self.dead_letters = dead_letters
        self.notifier = notifier
        self.gate = gate

    def _handler_for(self, scene: str) -> tuple[ScenePackageHandler, dict[str, Any]]:
        for contribution in self.registry.by_kind("ScenePackage"):
            if contribution.config.get("scene") == scene:
                factory = contribution.config.get("factory")
                if not factory:
                    break
                handler_cls = import_object(factory)
                return handler_cls(contribution.config), contribution.config
        raise DomainError("E008", f"未找到场景 {scene} 的应用包（未安装或已禁用）")

    def __call__(self, cmd: StartRunCommand) -> RunPipelineResult:
        # 先解析场景与闸门，再做幂等占位：闸门拒绝不应留下 CREATED 运行
        handler, config = self._handler_for(cmd.scene)
        gate_action = str(config.get("gate_action") or f"{cmd.scene}.report")
        decision = self.gate.decide(gate_action)
        if not decision.allowed:
            raise DomainError("E007", decision.reason)

        started = self.start_run(cmd)
        run = started.run
        if started.deduplicated or run.status is not RunStatus.CREATED:
            return RunPipelineResult(run, deduplicated=True)

        run.start(self.clock.now())
        self.repo.save(run)
        ctx = self.context_factory(run, config)
        scene_result: SceneResult | None = None
        try:
            scene_result = handler.run(ctx)
        except DomainError as exc:
            self._fail(run, exc)
            return RunPipelineResult(run)
        except Exception as exc:  # noqa: BLE001 - 未预期异常统一落 E008，不静默
            error = DomainError("E008", f"未预期异常: {exc}")
            self._fail(run, error, extra={"exception": repr(exc)})
            return RunPipelineResult(run)

        run.succeed(self.clock.now())
        self.repo.save(run)
        self.publisher.publish_all(run.pull_events())
        return RunPipelineResult(run, scene_result=scene_result)

    def _fail(self, run: Run, error: DomainError, extra: dict[str, Any] | None = None) -> None:
        """失败收口：run 置 FAILED + 异常记录 + 死信 + 告警，不静默丢弃。"""
        run.fail(error.code, error.layer, self.clock.now())
        self.repo.save(run)
        details = {"scene": run.scene, "app_id": run.app_id, **error.details, **(extra or {})}
        self.exceptions.record(error, run_id=run.run_id.value, details=details)
        self.dead_letters.record(
            error,
            run_id=run.run_id.value,
            payload={"run_id": run.run_id.value, "scene": run.scene, "details": details},
        )
        self.notifier.send(
            event="EVT-07",
            receiver="ops",
            title=f"执行异常 {error.code}/{error.layer}",
            body=f"运行 {run.run_id.value} 在 {run.scene} 失败：{error.message}",
            dedupe_key=f"EVT-07:{run.run_id.value}",
            payload={"run_id": run.run_id.value, "err_code": error.code, "err_layer": error.layer},
        )
        self.publisher.publish_all(run.pull_events())
