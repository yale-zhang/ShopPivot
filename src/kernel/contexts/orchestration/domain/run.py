"""Run 聚合（主文档表 8-4 / 表 8-19 代码骨架）。

不变量：
- run_id 全局唯一；
- 状态只能 CREATED→RUNNING→SUCCEEDED|FAILED|CANCELLED；
- 配置快照创建后不可变；
- FAILED 必带 err_code + err_layer。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from kernel.contexts.orchestration.domain.config_snapshot import ConfigSnapshot
from kernel.contexts.orchestration.domain.events import DomainEvent, RunFailed, RunStarted, RunSucceeded
from shared.errors.registry import DomainError, ERROR_SPECS
from shared.gate_level import GateLevel
from shared.run_id import RunId
from shared.types.values import Channel, StatWindow


class RunStatus(str, Enum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class NodeStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass(frozen=True, slots=True)
class NodeExecution:
    node_id: str
    status: NodeStatus
    cost_ms: int = 0
    channel: Channel | None = None
    err_code: str | None = None
    err_layer: str | None = None
    payload_digest: str | None = None


@dataclass
class Run:
    run_id: RunId
    app_id: str
    scene: str
    platform: str
    shop_id: str
    window: StatWindow
    trigger_type: str
    config_snapshot: ConfigSnapshot
    gate_level_max: GateLevel = GateLevel.L0_READ_ONLY
    requested_by: str = "system"
    status: RunStatus = RunStatus.CREATED
    nodes: list[NodeExecution] = field(default_factory=list)
    started_at: datetime | None = None
    ended_at: datetime | None = None
    err_code: str | None = None
    err_layer: str | None = None
    _events: list[DomainEvent] = field(default_factory=list, repr=False)

    @property
    def is_terminal(self) -> bool:
        return self.status in {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED}

    def _ensure(self, expected: RunStatus, action: str) -> None:
        if self.status is not expected:
            raise DomainError(
                "E006",
                f"{action} 需要状态 {expected.value}，当前 {self.status.value}",
                details={"run_id": self.run_id.value, "status": self.status.value},
            )

    def start(self, now: datetime) -> None:
        self._ensure(RunStatus.CREATED, "启动运行")
        self.status = RunStatus.RUNNING
        self.started_at = now
        self._events.append(
            RunStarted(
                run_id=self.run_id.value,
                app_id=self.app_id,
                config_snapshot_hash=self.config_snapshot.hash,
            )
        )

    def record_node(self, node: NodeExecution) -> None:
        if self.is_terminal:
            raise DomainError("E006", "运行已结束，不能再追加节点")
        if node.status is NodeStatus.FAILED:
            if not node.err_code or not node.err_layer:
                raise DomainError("E006", "失败节点必须带 err_code 与 err_layer")
            self._ensure_registered(node.err_code)
        replaced = False
        for index, existing in enumerate(self.nodes):
            if existing.node_id == node.node_id:
                self.nodes[index] = node
                replaced = True
                break
        if not replaced:
            self.nodes.append(node)

    def succeed(self, now: datetime) -> None:
        self._ensure(RunStatus.RUNNING, "标记成功")
        self.status = RunStatus.SUCCEEDED
        self.ended_at = now
        self._events.append(RunSucceeded(run_id=self.run_id.value, app_id=self.app_id))

    def fail(self, err_code: str, err_layer: str | None, now: datetime) -> None:
        if self.is_terminal:
            raise DomainError("E006", "运行已结束，不能重复置失败")
        self._ensure_registered(err_code)
        spec = ERROR_SPECS[err_code]
        self.status = RunStatus.FAILED
        self.err_code = err_code
        self.err_layer = err_layer or spec.default_layer
        self.ended_at = now
        self._events.append(
            RunFailed(run_id=self.run_id.value, err_code=err_code, err_layer=self.err_layer)
        )

    def cancel(self, now: datetime) -> None:
        if self.is_terminal:
            raise DomainError("E006", "运行已结束，不能取消")
        self.status = RunStatus.CANCELLED
        self.ended_at = now

    @staticmethod
    def _ensure_registered(err_code: str) -> None:
        if err_code not in ERROR_SPECS:
            raise DomainError("E008", f"未登记的错误码: {err_code}")

    def pull_events(self) -> list[DomainEvent]:
        events, self._events = self._events, []
        return events

    def config_view(self) -> dict[str, Any]:
        return self.config_snapshot.to_dict()
