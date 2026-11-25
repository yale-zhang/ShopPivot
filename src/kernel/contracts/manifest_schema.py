"""ModuleManifest 规范（主文档表 9-13 / 代码清单 9-1）。

manifest 是模块与 Kernel 之间唯一的契约：
- 只声明直接依赖（depends），循环依赖在启动期阻断；
- gate_level_max 是模块允许的最高写入级别，Kernel 在装配与 T4 路由双重校验；
- provides 的每一项都必须带稳定 ID，卸载时按 ID 精确摘除。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from shared.gate_level import GateLevel

NAME_RE = re.compile(r"^(mod|bundle)_[a-z0-9_]+$")
ID_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z0-9_@.-]+)*$")
TABLE_PREFIX_RE = re.compile(r"^[a-z][a-z0-9_]{1,15}$")
NAMESPACE_RE = re.compile(r"^modules\.[a-z0-9_]+$")
SCENE_RE = re.compile(r"^S\d{2}$")

DATA_ORDER = (
    "security/permissions",
    "data/metric_cards/",
    "data/workbench/",
    "data/seed/",
)


class ModuleCategory(str, Enum):
    CORE = "core"
    CAPABILITY = "capability"
    ADAPTER = "adapter"
    BUSINESS = "business"
    BUNDLE = "bundle"


class ContributionKind(str, Enum):
    SCENE_PACKAGE = "ScenePackage"
    PLATFORM_ADAPTER = "PlatformAdapter"
    METRIC_CARD = "MetricCard"
    GATE_RULE = "GateRule"
    WORKER_CAPABILITY = "WorkerCapability"
    WORKBENCH_CARD = "WorkbenchCard"
    NOTIFICATION_TEMPLATE = "NotificationTemplate"
    DATA_CONTRACT = "DataContract"
    COMPONENT = "Component"
    PERMISSION = "Permission"
    HEALTH_CHECK = "HealthCheck"
    CQ = "CQ"
    WRITE_ACTION = "WriteAction"
    SEMANTIC_CONCEPT = "SemanticConcept"


ALL_CONTRIBUTION_KINDS = frozenset(k.value for k in ContributionKind)


class Contribution(BaseModel):
    """一条扩展点贡献：kind + 稳定 ID + 配置（工厂/文件/参数）。"""

    model_config = ConfigDict(extra="forbid")

    kind: ContributionKind
    id: str = Field(min_length=1, max_length=128)
    config: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def _id_format(cls, value: str) -> str:
        if not ID_RE.match(value):
            raise ValueError(f"贡献 ID 非法: {value!r}（需小写、点分、稳定不可改名）")
        return value


class CapabilityRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["capability"] = "capability"
    name: str = Field(min_length=1, max_length=48)


class CredentialScope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["credential_scope"] = "credential_scope"
    scope: str = Field(min_length=1, max_length=96)


class DataContractRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["data_contract"] = "data_contract"
    dataset: str = Field(min_length=1, max_length=96)
    version: str = Field(min_length=1, max_length=16)


Requirement = CapabilityRequirement | CredentialScope | DataContractRequirement


class Hooks(BaseModel):
    model_config = ConfigDict(extra="forbid")

    on_install: str | None = None
    on_upgrade: str | None = None
    on_uninstall: str | None = None
    on_startup: str | None = None


class ModuleManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    version: str
    category: ModuleCategory
    depends: list[str] = Field(default_factory=list)
    api_compat: str = ">=1.0,<2.0"
    gate_level_max: GateLevel = GateLevel.L0_READ_ONLY
    requires: list[Requirement] = Field(default_factory=list)
    provides: list[Contribution] = Field(default_factory=list)
    scenes: list[str] = Field(default_factory=list)
    data: list[str] = Field(default_factory=list)
    config_namespace: str = ""
    table_prefix: str = ""
    hooks: Hooks = Field(default_factory=Hooks)
    migrations: str = "migrations/"
    health_checks: list[str] = Field(default_factory=list)
    cq: list[str] = Field(default_factory=list)
    license: str = "MIT"
    owner: str = "studio"
    enabled: bool = True
    auto_install: bool = False
    description: str = ""

    @field_validator("name")
    @classmethod
    def _name_format(cls, value: str) -> str:
        if not NAME_RE.match(value):
            raise ValueError(f"模块名非法: {value!r}（需 mod_/bundle_ 前缀 + 小写）")
        return value

    @field_validator("version")
    @classmethod
    def _semver(cls, value: str) -> str:
        try:
            Version(value)
        except InvalidVersion as exc:  # pragma: no cover - 由 pydantic 转成 ValidationError
            raise ValueError(f"版本号不是语义化版本: {value!r}") from exc
        return value

    @field_validator("api_compat")
    @classmethod
    def _api_compat(cls, value: str) -> str:
        try:
            SpecifierSet(value)
        except InvalidSpecifier as exc:
            raise ValueError(f"api_compat 不是合法的版本区间: {value!r}") from exc
        return value

    @field_validator("scenes")
    @classmethod
    def _scenes(cls, value: list[str]) -> list[str]:
        for scene in value:
            if not SCENE_RE.match(scene):
                raise ValueError(f"场景编号非法: {scene!r}")
        return value

    @model_validator(mode="after")
    def _category_rules(self) -> "ModuleManifest":
        if self.gate_level_max is GateLevel.L3_FORBIDDEN:
            raise ValueError("gate_level_max 只能是 L0/L1/L2（L3 表示禁止自动化，不能作为上限）")
        if self.category is ModuleCategory.BUNDLE:
            if not self.depends:
                raise ValueError("bundle 组合包必须声明 depends")
            if self.provides:
                raise ValueError("bundle 不得包含业务逻辑（provides 必须为空）")
        if self.category is ModuleCategory.CORE and not self.provides:
            raise ValueError("core 模块必须提供至少一项扩展点贡献")
        if not self.config_namespace:
            self.config_namespace = f"modules.{self.name}"
        if not self.table_prefix:
            self.table_prefix = self.name.removeprefix("mod_")[:10]
        if not NAMESPACE_RE.match(self.config_namespace):
            raise ValueError(f"config_namespace 非法: {self.config_namespace!r}")
        if not TABLE_PREFIX_RE.match(self.table_prefix):
            raise ValueError(f"table_prefix 非法: {self.table_prefix!r}")
        return self

    def requirement_capabilities(self) -> set[str]:
        return {r.name for r in self.requires if isinstance(r, CapabilityRequirement)}

    def requirement_scopes(self) -> set[str]:
        return {r.scope for r in self.requires if isinstance(r, CredentialScope)}

    def requirement_contracts(self) -> set[tuple[str, str]]:
        return {
            (r.dataset, r.version)
            for r in self.requires
            if isinstance(r, DataContractRequirement)
        }

    def contribution_ids(self) -> dict[str, str]:
        return {c.id: c.kind.value for c in self.provides}


@dataclass
class ManifestIssue:
    check: str
    module: str
    message: str
    fatal: bool = False


def data_file_rank(path: str) -> int | None:
    for index, prefix in enumerate(DATA_ORDER):
        if path.startswith(prefix):
            return index
    return None


def validate_data_order(module: str, files: list[str]) -> list[ManifestIssue]:
    issues: list[ManifestIssue] = []
    last_rank = -1
    for path in files:
        rank = data_file_rank(path)
        if rank is None:
            issues.append(
                ManifestIssue("M06", module, f"data 文件未登记到已知分区: {path}", fatal=True)
            )
            continue
        if rank < last_rank:
            issues.append(
                ManifestIssue(
                    "M06",
                    module,
                    f"data 顺序非法: {path}（必须 permissions → metric_cards → workbench → seed）",
                    fatal=True,
                )
            )
        last_rank = rank
    return issues


@dataclass
class ModuleLoadState:
    name: str
    version: str
    category: ModuleCategory
    state: str
    enabled: bool
    contributions: list[str] = field(default_factory=list)
    blocking_reason: str | None = None
    checks_passed: list[str] = field(default_factory=list)
