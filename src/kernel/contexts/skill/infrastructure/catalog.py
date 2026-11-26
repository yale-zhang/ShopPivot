"""本地 Skill 目录：skills.lock + 适配清单。

锁文件固定版本与状态；清单声明能力、信任、命令白名单与适配器。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from kernel.contexts.skill.domain.models import (
    SkillBinding,
    SkillCapability,
    SkillManifest,
    SkillRisk,
    TrustLevel,
)
from kernel.contexts.skill.domain.ports import SkillCatalogPort


class SkillCatalogError(Exception):
    pass


class LocalSkillCatalog(SkillCatalogPort):
    def __init__(self, lock_path: str | Path, root: str | Path = ".") -> None:
        self.lock_path = Path(lock_path)
        self.root = Path(root)
        self._manifests: dict[str, SkillManifest] = {}
        self._bindings: list[SkillBinding] = []
        self._load()

    def _load(self) -> None:
        if not self.lock_path.is_file():
            raise SkillCatalogError(f"skills.lock 不存在: {self.lock_path}")
        payload = yaml.safe_load(self.lock_path.read_text(encoding="utf-8")) or {}
        items = payload.get("skills")
        if not isinstance(items, list):
            raise SkillCatalogError("skills.lock 缺少 skills 列表")
        for item in items:
            if not isinstance(item, dict):
                raise SkillCatalogError("skills.lock 条目必须是对象")
            manifest_path = self.root / str(item.get("manifest", ""))
            if not manifest_path.is_file():
                raise SkillCatalogError(f"Skill 清单不存在: {manifest_path}")
            raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
            manifest = self._parse_manifest(raw, item, str(manifest_path))
            if manifest.id in self._manifests:
                raise SkillCatalogError(f"Skill 重复: {manifest.id}")
            self._manifests[manifest.id] = manifest
            for binding in item.get("bindings") or []:
                self._bindings.append(
                    SkillBinding(
                        skill_id=manifest.id,
                        platform=str(binding.get("platform", "*")),
                        shop_id=str(binding.get("shop_id", "*")),
                        enabled=bool(binding.get("enabled", True)),
                        priority=int(binding.get("priority", 10)),
                        config=dict(binding.get("config") or {}),
                    )
                )
        if not self._manifests:
            raise SkillCatalogError("skills.lock 没有可用 Skill")

    @staticmethod
    def _parse_manifest(raw: dict[str, Any], lock_item: dict[str, Any], manifest_path: str) -> SkillManifest:
        skill_id = str(raw.get("id") or lock_item.get("id") or "")
        version = str(raw.get("version") or lock_item.get("version") or "")
        if not skill_id or not version:
            raise SkillCatalogError("Skill 清单缺少 id/version")
        if lock_item.get("version") and str(lock_item["version"]) != version:
            raise SkillCatalogError(
                f"Skill {skill_id} 版本与锁文件不一致: {version} != {lock_item['version']}"
            )
        capabilities_raw = raw.get("capabilities") or []
        if not capabilities_raw:
            raise SkillCatalogError(f"Skill {skill_id} 没有声明能力")
        capabilities: list[SkillCapability] = []
        for item in capabilities_raw:
            name = str(item.get("name", "")).strip()
            if not name:
                raise SkillCatalogError(f"Skill {skill_id} 能力缺少 name")
            try:
                risk = SkillRisk(str(item.get("risk", "L0")))
            except ValueError as exc:
                raise SkillCatalogError(f"Skill {skill_id} 能力 {name} 风险非法") from exc
            capabilities.append(
                SkillCapability(name=name, risk=risk, description=str(item.get("description", "")))
            )
        adapter = str(raw.get("adapter", ""))
        if not adapter or ":" not in adapter:
            raise SkillCatalogError(f"Skill {skill_id} 缺少 adapter（module:Class）")
        try:
            trust = TrustLevel(str(raw.get("trust", "untrusted")))
        except ValueError as exc:
            raise SkillCatalogError(f"Skill {skill_id} 信任等级非法") from exc
        return SkillManifest(
            id=skill_id,
            version=version,
            publisher=str(raw.get("publisher", "")),
            trust=trust,
            license=str(raw.get("license", "")),
            adapter=adapter,
            capabilities=tuple(capabilities),
            description=str(raw.get("description", "")),
            entrypoints=dict(raw.get("entrypoints") or {}),
            limits=dict(raw.get("limits") or {}),
            credentials=tuple(str(item) for item in (raw.get("credentials") or [])),
            config=dict(raw.get("config") or {}),
            checksum=str(lock_item.get("checksum", "")),
            status=str(lock_item.get("status", "adapter-only")),
            manifest_path=str(manifest_path),
        )

    def all(self) -> list[SkillManifest]:
        return sorted(self._manifests.values(), key=lambda item: item.id)

    def get(self, skill_id: str) -> SkillManifest | None:
        return self._manifests.get(skill_id)

    def bindings(self) -> list[SkillBinding]:
        return list(self._bindings)

    def find(
        self, capability: str, platform: str, shop_id: str
    ) -> tuple[SkillManifest, SkillBinding] | None:
        matches: list[tuple[int, int, SkillManifest, SkillBinding]] = []
        for manifest in self._manifests.values():
            if manifest.capability(capability) is None:
                continue
            for binding in self._bindings:
                if binding.skill_id != manifest.id or not binding.enabled:
                    continue
                if binding.matches(platform, shop_id):
                    matches.append((binding.priority, manifest.trust.rank, manifest, binding))
        if not matches:
            return None
        matches.sort(key=lambda item: (-item[0], -item[1], item[2].id))
        _, _, manifest, binding = matches[0]
        return manifest, binding
