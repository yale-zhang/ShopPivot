"""Skill 生命周期：校验/安装（清单级）、启用/停用、按店铺绑定。

S2a 只做清单校验与登记，真实包下载/解压/签名在 S2b；所有状态落库，便于审计。
"""
from __future__ import annotations

import hashlib
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kernel.contexts.skill.domain.models import (
    SkillBinding,
    SkillInstallation,
    SkillRisk,
    TrustLevel,
)
from kernel.contexts.skill.infrastructure.package import (
    SkillPackageError,
    package_checksum,
    safe_extract,
)
from kernel.contexts.skill.domain.ports import (
    SkillBindingRepository,
    SkillCatalogPort,
    SkillInstallationRepository,
)
from shared.errors.registry import DomainError

import yaml


class SkillLifecycleService:
    def __init__(
        self,
        catalog: SkillCatalogPort,
        installations: SkillInstallationRepository,
        bindings: SkillBindingRepository,
        *,
        settings: Any = None,
    ) -> None:
        self.catalog = catalog
        self.installations = installations
        self.bindings = bindings
        self.settings = settings

    def install(self, skill_id: str, *, actor: str = "owner") -> SkillInstallation:
        manifest = self.catalog.get(skill_id)
        if manifest is None:
            raise DomainError("E008", f"Skill 不存在: {skill_id}", status_override=404)
        if manifest.trust is TrustLevel.UNTRUSTED:
            raise DomainError("E006", f"未信任 Skill 禁止安装: {skill_id}")
        allowlist = list(getattr(self.settings, "skill_publisher_allowlist", []) or [])
        if manifest.trust in {TrustLevel.OFFICIAL, TrustLevel.VERIFIED} and allowlist:
            if manifest.publisher not in allowlist:
                raise DomainError(
                    "E006", f"Skill 发布者不在白名单: {manifest.publisher}"
                )
        if manifest.trust is TrustLevel.COMMUNITY and any(
            item.risk is not SkillRisk.L0 for item in manifest.capabilities
        ):
            raise DomainError("E006", "社区 Skill 只能声明只读能力")
        checksum = _manifest_checksum(manifest.manifest_path)
        if manifest.checksum not in {"", "adapter-only"} and manifest.checksum != checksum:
            raise DomainError("E006", f"Skill 校验和不匹配: {skill_id}")
        installation = SkillInstallation(
            skill_id=skill_id,
            version=manifest.version,
            status="INSTALLED",
            checksum=checksum,
            manifest_path=manifest.manifest_path,
            installed_by=actor,
            details={"kind": "manifest-checksum", "trust": manifest.trust.value},
            installed_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self.installations.upsert(installation)
        return installation

    def install_package(
        self, skill_id: str, package_path: str, *, actor: str = "owner"
    ) -> SkillInstallation:
        manifest = self.catalog.get(skill_id)
        if manifest is None:
            raise DomainError("E008", f"Skill 不存在: {skill_id}", status_override=404)
        archive = self._resolve_package(package_path)
        package_hash = package_checksum(archive)
        if manifest.checksum not in {"", "adapter-only"} and manifest.checksum != package_hash:
            raise DomainError("E006", f"Skill 包校验和不匹配: {skill_id}")
        storage = Path(getattr(self.settings, "storage_dir", "storage"))
        root = storage / "skills"
        root.mkdir(parents=True, exist_ok=True)
        temp = root / f".install-{skill_id}-{datetime.now(UTC).timestamp():.0f}"
        if temp.exists():
            shutil.rmtree(temp)
        try:
            try:
                files = safe_extract(archive, temp)
            except SkillPackageError as exc:
                raise DomainError("E006", str(exc)) from exc
            manifest_path = temp / "skill.yaml"
            if not manifest_path.is_file():
                raise DomainError("E006", "Skill 包缺少 skill.yaml")
            raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
            if str(raw.get("id")) != manifest.id or str(raw.get("version")) != manifest.version:
                raise DomainError("E006", "Skill 包 id/version 与锁文件不一致")
            if str(raw.get("adapter")) != manifest.adapter:
                raise DomainError("E006", "Skill 包 adapter 与登记清单不一致")
            lock = temp / "skills.lock"
            lock.write_text(
                yaml.safe_dump(
                    {
                        "version": 1,
                        "skills": [
                            {
                                "id": manifest.id,
                                "version": manifest.version,
                                "manifest": "skill.yaml",
                                "status": "installed",
                            }
                        ],
                    },
                    allow_unicode=True,
                ),
                encoding="utf-8",
            )
            from kernel.contexts.skill.infrastructure.catalog import LocalSkillCatalog

            try:
                LocalSkillCatalog(lock, root=temp)
            except Exception as exc:  # noqa: BLE001
                raise DomainError("E006", f"Skill 包清单非法: {exc}") from exc
            lock.unlink()
            destination = root / manifest.id / manifest.version
            if destination.exists():
                shutil.rmtree(destination)
            destination.parent.mkdir(parents=True, exist_ok=True)
            temp.rename(destination)
            manifest_hash = _manifest_checksum(str(destination / "skill.yaml"))
            installation = SkillInstallation(
                skill_id=skill_id,
                version=manifest.version,
                status="INSTALLED",
                checksum=manifest_hash,
                manifest_path=str(destination / "skill.yaml"),
                installed_by=actor,
                details={
                    "kind": "package",
                    "package_checksum": package_hash,
                    "package_path": str(archive),
                    "files": files,
                },
                installed_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            self.installations.upsert(installation)
            return installation
        finally:
            if temp.exists():
                shutil.rmtree(temp, ignore_errors=True)

    def _resolve_package(self, package_path: str) -> Path:
        storage = Path(getattr(self.settings, "storage_dir", "storage"))
        root = (storage / "skill_packages").resolve()
        root.mkdir(parents=True, exist_ok=True)
        candidate = Path(package_path)
        if not candidate.is_absolute():
            candidate = root / candidate
        resolved = candidate.resolve()
        if root not in resolved.parents and resolved != root:
            raise DomainError("E006", "Skill 包必须放在受控目录 skill_packages 下")
        if resolved.suffix != ".zip" or not resolved.is_file():
            raise DomainError("E006", f"Skill 包不存在或不是 zip: {package_path}")
        return resolved

    def verify(self, skill_id: str) -> dict[str, Any]:
        installation = self.installations.get(skill_id)
        if installation is None:
            raise DomainError("E008", f"Skill 未安装: {skill_id}", status_override=409)
        current = _manifest_checksum(installation.manifest_path)
        ok = bool(installation.checksum) and current == installation.checksum
        return {
            "skill_id": skill_id,
            "ok": ok,
            "expected": installation.checksum,
            "actual": current,
        }

    def set_enabled(
        self, skill_id: str, enabled: bool, *, actor: str = "owner"
    ) -> SkillInstallation:
        installation = self.installations.get(skill_id)
        if installation is None:
            raise DomainError("E008", f"Skill 未安装: {skill_id}", status_override=409)
        installation.status = "ENABLED" if enabled else "DISABLED"
        installation.updated_at = datetime.now(UTC)
        installation.installed_by = actor
        self.installations.upsert(installation)
        return installation

    def list_bindings(self, skill_id: str) -> list[SkillBinding]:
        return self.bindings.list_for_skill(skill_id)

    def set_binding(
        self,
        skill_id: str,
        *,
        platform: str,
        shop_id: str,
        enabled: bool = True,
        priority: int = 10,
        credential_ref: str = "",
        config: dict[str, Any] | None = None,
        actor: str = "owner",
    ) -> SkillBinding:
        if self.catalog.get(skill_id) is None:
            raise DomainError("E008", f"Skill 不存在: {skill_id}", status_override=404)
        binding = SkillBinding(
            skill_id=skill_id,
            platform=platform or "*",
            shop_id=shop_id or "*",
            enabled=enabled,
            priority=max(0, min(priority, 1000)),
            credential_ref=credential_ref,
            config=dict(config or {}),
        )
        self.bindings.upsert(binding)
        return binding

    def remove_binding(self, skill_id: str, platform: str, shop_id: str) -> None:
        self.bindings.delete(skill_id, platform, shop_id)

    def ensure_usable(self, skill_id: str) -> None:
        installation = self.installations.get(skill_id)
        if installation is not None and installation.status in {"DISABLED", "FAILED"}:
            raise DomainError("E008", f"Skill 已停用/失败: {skill_id}")


def _manifest_checksum(path: str) -> str:
    if not path:
        return ""
    try:
        raw = Path(path).read_bytes()
    except OSError:
        return ""
    return hashlib.sha256(raw).hexdigest()
