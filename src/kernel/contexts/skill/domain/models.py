"""Skill 运行时的领域模型。

Skill 是外部能力包；店枢只信任其“声明 + 校验 + 沙箱输出”，不把 Skill 当控制面。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class TrustLevel(str, Enum):
    OFFICIAL = "official"
    VERIFIED = "verified"
    COMMUNITY = "community"
    UNTRUSTED = "untrusted"

    @property
    def rank(self) -> int:
        return {
            TrustLevel.UNTRUSTED: 0,
            TrustLevel.COMMUNITY: 1,
            TrustLevel.VERIFIED: 2,
            TrustLevel.OFFICIAL: 3,
        }[self]


class SkillRisk(str, Enum):
    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"

    @property
    def rank(self) -> int:
        return int(self.value[1])

    @property
    def label(self) -> str:
        return {
            SkillRisk.L0: "只读",
            SkillRisk.L1: "内部记录",
            SkillRisk.L2: "外部写（需审批）",
            SkillRisk.L3: "支付/财务（禁止自动化）",
        }[self]


@dataclass(frozen=True)
class SkillCapability:
    name: str
    risk: SkillRisk
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "risk": self.risk.value,
            "risk_label": self.risk.label,
            "description": self.description,
        }


@dataclass(frozen=True)
class SkillManifest:
    id: str
    version: str
    publisher: str
    trust: TrustLevel
    license: str
    adapter: str
    capabilities: tuple[SkillCapability, ...]
    description: str = ""
    entrypoints: dict[str, Any] = field(default_factory=dict)
    limits: dict[str, Any] = field(default_factory=dict)
    credentials: tuple[str, ...] = ()
    config: dict[str, Any] = field(default_factory=dict)
    checksum: str = ""
    status: str = "adapter-only"
    manifest_path: str = ""

    def capability(self, name: str) -> SkillCapability | None:
        return next((item for item in self.capabilities if item.name == name), None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "version": self.version,
            "publisher": self.publisher,
            "trust": self.trust.value,
            "license": self.license,
            "adapter": self.adapter,
            "description": self.description,
            "capabilities": [item.to_dict() for item in self.capabilities],
            "entrypoints": self.entrypoints,
            "limits": self.limits,
            "credentials": list(self.credentials),
            "config": self.config,
            "checksum": self.checksum,
            "status": self.status,
            "manifest_path": self.manifest_path,
        }


@dataclass(frozen=True)
class SkillBinding:
    skill_id: str
    platform: str = "*"
    shop_id: str = "*"
    enabled: bool = True
    priority: int = 10
    credential_ref: str = ""
    config: dict[str, Any] = field(default_factory=dict)

    def matches(self, platform: str, shop_id: str) -> bool:
        platform_ok = self.platform in {"*", platform}
        shop_ok = self.shop_id in {"*", shop_id}
        return platform_ok and shop_ok


@dataclass(frozen=True)
class SkillInvocation:
    manifest: SkillManifest
    binding: SkillBinding
    platform: str
    shop_id: str
    run_id: str = ""
    capability: str = ""
    requested_by: str = "system"
    settings: Any = None


@dataclass(frozen=True)
class SkillOutput:
    status: str
    data: Any = None
    evidence: list[dict[str, Any]] = field(default_factory=list)
    cost: float = 0.0
    latency_ms: int = 0
    raw: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == "SUCCEEDED"


@dataclass
class SkillInstallation:
    skill_id: str
    version: str
    status: str
    checksum: str = ""
    manifest_path: str = ""
    installed_by: str = "owner"
    details: dict[str, Any] = field(default_factory=dict)
    installed_at: datetime | None = None
    updated_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "version": self.version,
            "status": self.status,
            "checksum": self.checksum,
            "manifest_path": self.manifest_path,
            "installed_by": self.installed_by,
            "details": self.details,
            "installed_at": self.installed_at.isoformat() if self.installed_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


@dataclass
class SkillRun:
    run_id: str
    skill_id: str
    skill_version: str
    capability: str
    scene: str
    platform: str
    shop_id: str
    status: str
    input_digest: str = ""
    output_digest: str = ""
    latency_ms: int = 0
    error_code: str | None = None
    created_at: datetime | None = None


class SkillUnavailable(Exception):
    """没有匹配的 Skill / 绑定 / 适配器，或执行失败。fail-closed。"""
