"""用例：开始一次运行（T0 触发）。

- 幂等键必填：重复触发返回同一 run，不产生第二次采集；
- 配置快照在创建时固化，后续口径/阈值变更不影响已创建的运行。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

from kernel.contexts.orchestration.domain.config_snapshot import ConfigSnapshot
from kernel.contexts.orchestration.domain.ports import (
    Clock,
    EventPublisher,
    IdempotencyStore,
    RunRepository,
)
from kernel.contexts.orchestration.domain.run import Run, RunStatus
from shared.gate_level import GateLevel
from shared.run_id import RunId
from shared.types.values import StatWindow


class SnapshotBuilder(Protocol):
    def build(self, *, platform: str, shop_id: str, scene: str) -> dict[str, Any]: ...


@dataclass(frozen=True)
class StartRunCommand:
    app_id: str
    scene: str
    platform: str
    shop_id: str
    window_start: date
    window_end: date
    trigger_type: str = "MANUAL"
    requested_by: str = "system"
    idempotency_key: str = ""
    config_ref: str | None = None
    params: dict[str, object] | None = None


@dataclass(frozen=True)
class StartRunResult:
    run: Run
    deduplicated: bool


class StartRunUseCase:
    def __init__(
        self,
        repo: RunRepository,
        idempotency: IdempotencyStore,
        snapshots: SnapshotBuilder,
        publisher: EventPublisher,
        clock: Clock,
        *,
        gate_level_max: GateLevel = GateLevel.L0_READ_ONLY,
    ) -> None:
        self.repo = repo
        self.idempotency = idempotency
        self.snapshots = snapshots
        self.publisher = publisher
        self.clock = clock
        self.gate_level_max = gate_level_max

    def __call__(self, cmd: StartRunCommand) -> StartRunResult:
        if not cmd.idempotency_key:
            raise ValueError("idempotency_key 必填")

        existing_id = self.idempotency.get(cmd.idempotency_key)
        if existing_id:
            existing = self.repo.get(RunId.parse(existing_id))
            if existing is not None:
                return StartRunResult(existing, deduplicated=True)

        run_id = RunId.new()
        payload = self.snapshots.build(
            platform=cmd.platform, shop_id=cmd.shop_id, scene=cmd.scene
        )
        payload.update(
            {
                "app_id": cmd.app_id,
                "scene": cmd.scene,
                "platform": cmd.platform,
                "shop_id": cmd.shop_id,
                "window": [cmd.window_start.isoformat(), cmd.window_end.isoformat()],
                "config_ref": cmd.config_ref,
                "params": cmd.params or {},
                "gate_level_max": self.gate_level_max.value,
                "schema_version": "1.0",
            }
        )
        run = Run(
            run_id=run_id,
            app_id=cmd.app_id,
            scene=cmd.scene,
            platform=cmd.platform,
            shop_id=cmd.shop_id,
            window=StatWindow(cmd.window_start, cmd.window_end),
            trigger_type=cmd.trigger_type,
            config_snapshot=ConfigSnapshot.build(payload),
            gate_level_max=self.gate_level_max,
            requested_by=cmd.requested_by,
            status=RunStatus.CREATED,
        )
        claimed = self.idempotency.claim(cmd.idempotency_key, run_id.value)
        if claimed is not None:
            existing = self.repo.get(RunId.parse(claimed))
            if existing is not None:
                return StartRunResult(existing, deduplicated=True)
            raise RuntimeError(f"幂等键 {cmd.idempotency_key} 已占用但运行不存在: {claimed}")
        self.repo.add(run)
        return StartRunResult(run, deduplicated=False)
