"""扩展点清单（主文档表 9-15）。

模块不直接改 Kernel 代码，只向注册表贡献；Kernel 在 T0~T6 各节点按类型消费。
所有贡献都带稳定 ID，禁用/卸载时按 ID 精确摘除。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from shared.gate_level import GateLevel

if TYPE_CHECKING:  # pragma: no cover - 仅类型检查，避免与上下文形成运行期环
    from kernel.contexts.integration.domain.models import FetchSpec
    from kernel.contexts.metric_data.domain.canonical_record import CanonicalRecord
    from kernel.contexts.metric_data.domain.ports import RawPayload
    from kernel.contexts.approval.domain.write_plan import WritePlan
    from kernel.contexts.orchestration.application.scene_context import SceneContext
    from shared.types.values import Channel


@dataclass
class SceneResult:
    report_id: str | None = None
    artifact_ref: str | None = None
    metrics_written: int = 0
    gate_level: GateLevel = GateLevel.L0_READ_ONLY
    details: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class ScenePackageHandler(Protocol):
    """一个场景应用包的入口；只能通过 Kernel 端口访问数据与执行面。"""

    scene: str
    gate_level: GateLevel

    def run(self, ctx: "SceneContext") -> SceneResult: ...


@dataclass
class WriteActionRequest:
    platform: str
    shop_id: str
    rows: list[dict[str, Any]]
    requested_by: str = "system"
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionPlan:
    rows: list[dict[str, Any]]
    before_snapshot: dict[str, Any]
    summary: str
    impact_scope: str
    rollback_plan: str
    evidence: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ActionResult:
    verified: bool
    applied_rows: list[dict[str, Any]]
    after_shot: str
    details: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class WriteActionHandler(Protocol):
    """L2 写入动作扩展点：模块只声明"怎么做"，审批与执行许可由 Kernel 闸门控制。"""

    action_code: str

    def build(self, request: WriteActionRequest) -> ActionPlan: ...

    def apply(self, plan: "WritePlan") -> ActionResult: ...

    def verify(self, plan: "WritePlan") -> bool: ...

    def compensate(self, plan: "WritePlan") -> bool: ...


@runtime_checkable
class PlatformAdapterPort(Protocol):
    """平台防腐层：平台差异挡在这里，只产出 CanonicalRecord。"""

    platform: str

    def fetch(self, spec: "FetchSpec", channel: "Channel") -> "RawPayload": ...

    def to_canonical(self, raw: "RawPayload") -> "list[CanonicalRecord]": ...


@runtime_checkable
class HealthCheckPort(Protocol):
    id: str

    def check(self) -> tuple[bool, str]: ...


class WorkbenchCardSpec(BaseModel):
    """工作台卡片贡献（表 3-17 / 表 9-15）。"""

    model_config = ConfigDict(extra="forbid")

    card_id: str = Field(pattern=r"^card\.[a-z][a-z0-9_]*$")
    page_id: str = Field(pattern=r"^P\d{2}$")
    module: str
    title: str
    slot: str = "main"
    data_endpoint: str = ""
    required_context: list[str] = Field(default_factory=lambda: ["platform", "shop_id", "window"])
    empty_state_copy: str = "暂无可展示内容"
    order: int = 100


class NotificationTemplateSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: str = Field(pattern=r"^EVT-\d{2}$")
    channel: str = "CONSOLE"
    title: str
    body: str


class DataContractSpec(BaseModel):
    """DataContract 贡献的结构（表 9-15 / S5 数据合同）。"""

    model_config = ConfigDict(extra="forbid")

    dataset: str = Field(min_length=1, max_length=96)
    version: str = Field(default="1", max_length=16)
    platform: str = ""
    required_fields: list[str] = Field(default_factory=list)
    enum_sets: dict[str, list[str]] = Field(default_factory=dict)
    quality_tests: list[str] = Field(default_factory=list)
    api_version: str = ""
    owner: str = "studio"


class PermissionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str = Field(pattern=r"^(OWNER|EDITOR|VIEWER)$")
    capability: str


class MetricCardFileSpec(BaseModel):
    """data/metric_cards/*.yaml 的结构（口径卡可执行规格）。"""

    model_config = ConfigDict(extra="forbid")

    metric_code: str
    display_name: str
    version: str
    display_order: int = 100
    unit: str
    precision: int = Field(ge=0, le=6)
    additivity: str = Field(pattern=r"^(ADDITIVE|RATIO|NON_ADDITIVE)$")
    formula: str
    denominator: str | None = None
    null_policy: str = "NOT_APPLICABLE"
    platform: str = "*"
    source_mapping: str = ""
    description: str = ""
    concept_uri: str = ""
    synonyms: list[str] = Field(default_factory=list)
    probe_sql_template: str = ""
    quality_tests: list[str] = Field(default_factory=list)
    effective_from: str = ""
    breaking_change: bool = False
