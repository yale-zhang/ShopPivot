"""执行面 Worker API 契约（主文档表 6-10 / §8.11）。

约束：
- `/job/start`、`/job/query`、`/suggest` 只接受只读/建议 token，不下发写入权限；
- `/write` 仅闸门服务可调，一次性 task token 短时效且绑定 task_id；
- 结果回流统一走 `/callback`，禁止执行面直写数据库。
"""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from shared.gate_level import GateLevel
from shared.types.values import Channel


class TriggerType(str, Enum):
    SCHEDULE = "SCHEDULE"
    EVENT = "EVENT"
    MANUAL = "MANUAL"


class JobStatus(str, Enum):
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


class NodeExecutionView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    status: NodeStatus
    cost_ms: int | None = None
    err_code: str | None = None
    err_layer: str | None = None


class ErrorEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    layer: str
    message: str
    user_message: str
    retryable: bool
    details: dict[str, Any] = Field(default_factory=dict)


class JobStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app_id: str = Field(min_length=1, max_length=64)
    scene: str = Field(pattern=r"^S\d{2}$")
    platform: str = Field(min_length=1, max_length=32)
    shop_id: str = Field(min_length=1, max_length=64)
    window_start: date
    window_end: date
    trigger_type: TriggerType = TriggerType.MANUAL
    config_ref: str | None = None
    idempotency_key: str = Field(min_length=3, max_length=200)
    requested_by: str = Field(default="system", max_length=64)

    @model_validator(mode="after")
    def _check_window(self) -> "JobStartRequest":
        if self.window_end < self.window_start:
            raise ValueError("window_end 不能早于 window_start")
        return self


class JobStartResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    status: JobStatus
    accepted_at: datetime
    deduplicated: bool = False


class JobQueryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    app_id: str
    scene: str
    platform: str
    shop_id: str
    status: JobStatus
    trigger_type: TriggerType
    started_at: datetime | None = None
    ended_at: datetime | None = None
    config_snapshot_hash: str | None = None
    gate_level_max: GateLevel = GateLevel.L0_READ_ONLY
    nodes: list[NodeExecutionView] = Field(default_factory=list)
    report_refs: list[str] = Field(default_factory=list)


class ProposalItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: str
    before: str | None = None
    after: str | None = None
    impact: str | None = None
    evidence_ref: str | None = None


class SuggestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    scope: str = ""


class SuggestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    gate_level: GateLevel
    proposals: list[ProposalItem] = Field(default_factory=list)
    impact_scope: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)


class WriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    token: str
    change_order_no: str
    confirmed_values: list[dict[str, Any]] = Field(default_factory=list)


class WriteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool
    task_id: str
    message: str


class CallbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    node_id: str
    status: NodeStatus
    cost_ms: int = 0
    err_code: str | None = None
    err_layer: str | None = None
    payload_digest: str | None = None
    outputs: list[dict[str, Any]] = Field(default_factory=list)
    screenshot_refs: list[str] = Field(default_factory=list)
    channel: Channel | None = None


class HeartbeatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    worker_id: str
    kind: Literal["HEADLESS", "DESKTOP"]
    status: Literal["ONLINE", "BUSY", "OFFLINE"] = "ONLINE"
    capabilities: list[str] = Field(default_factory=list)
    queue_depth: int = 0


class CapabilitiesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    worker_id: str
    kind: Literal["HEADLESS", "DESKTOP"]
    capabilities: list[str]
    kernel_api: str
