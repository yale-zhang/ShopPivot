"""Skill 端口。"""
from __future__ import annotations

from typing import Any, Protocol, Sequence

from kernel.contexts.skill.domain.models import (
    SkillBinding,
    SkillCapability,
    SkillInstallation,
    SkillInvocation,
    SkillManifest,
    SkillOutput,
    SkillRun,
)


class SkillCatalogPort(Protocol):
    def all(self) -> list[SkillManifest]: ...

    def get(self, skill_id: str) -> SkillManifest | None: ...

    def find(self, capability: str, platform: str, shop_id: str) -> tuple[SkillManifest, SkillBinding] | None: ...

    def bindings(self) -> list[SkillBinding]: ...


class SkillAdapterPort(Protocol):
    def execute(self, invocation: SkillInvocation, payload: dict[str, Any]) -> SkillOutput: ...


class SkillInstallationRepository(Protocol):
    def get(self, skill_id: str) -> SkillInstallation | None: ...

    def upsert(self, installation: SkillInstallation) -> None: ...

    def all(self) -> list[SkillInstallation]: ...


class SkillBindingRepository(Protocol):
    def get(self, skill_id: str, platform: str, shop_id: str) -> SkillBinding | None: ...

    def list_for_skill(self, skill_id: str) -> list[SkillBinding]: ...

    def upsert(self, binding: SkillBinding) -> None: ...

    def delete(self, skill_id: str, platform: str, shop_id: str) -> None: ...


class SkillRunRepository(Protocol):
    def record(self, run: SkillRun) -> None: ...

    def recent(self, limit: int = 50) -> list[SkillRun]: ...


class SkillCapabilityIndex(Protocol):
    def capabilities(self) -> Sequence[SkillCapability]: ...
