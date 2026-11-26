"""P14 技能中心：目录与运行记录（S0 只读）。"""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from bootstrap.container import AppContainer
from bootstrap.deps import get_container, require
from kernel.contexts.identity.domain.account import Permission
from kernel.contexts.observability.domain.models import AuditEntry
from shared.errors.registry import DomainError

router = APIRouter(prefix="/api/v1", tags=["skills"])


class InstallRequest(BaseModel):
    source: Literal["manifest", "package"] = "manifest"
    package_path: str | None = None


class BindingRequest(BaseModel):
    platform: str = Field(default="*", max_length=32)
    shop_id: str = Field(default="*", max_length=64)
    enabled: bool = True
    priority: int = Field(default=10, ge=0, le=1000)
    credential_ref: str = Field(default="", max_length=128)
    config: dict[str, Any] = Field(default_factory=dict)


def _audit(container: AppContainer, actor: str, action: str, skill_id: str, after: dict[str, Any]) -> None:
    container.audit.record(
        AuditEntry(
            actor=actor,
            action=action,
            object_type="skill",
            object_id=skill_id,
            after=after,
        )
    )


def _run_dict(run: Any) -> dict[str, Any]:
    return {
        "run_id": run.run_id,
        "skill_id": run.skill_id,
        "skill_version": run.skill_version,
        "capability": run.capability,
        "scene": run.scene,
        "platform": run.platform,
        "shop_id": run.shop_id,
        "status": run.status,
        "latency_ms": run.latency_ms,
        "error_code": run.error_code,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


@router.get("/skills/catalog")
def skill_catalog(
    container: AppContainer = Depends(get_container),
    user=Depends(require(Permission.VIEW_AUDIT)),
) -> dict[str, Any]:
    items = []
    installations = {item.skill_id: item for item in container.skill_installations.all()}
    for manifest in container.skill_catalog.all():
        item = manifest.to_dict()
        installation = installations.get(manifest.id)
        if installation is not None:
            item["status"] = installation.status
            item["checksum"] = installation.checksum
            item["installed_at"] = installation.installed_at.isoformat() if installation.installed_at else None
        dynamic = container.skill_bindings.list_for_skill(manifest.id)
        static = [b for b in container.skill_catalog.bindings() if b.skill_id == manifest.id]
        chosen = dynamic or static
        item["bindings"] = [
            {
                "platform": binding.platform,
                "shop_id": binding.shop_id,
                "enabled": binding.enabled,
                "priority": binding.priority,
                "credential_ref": getattr(binding, "credential_ref", ""),
            }
            for binding in chosen
        ]
        items.append(item)
    return {
        "items": items,
        "count": len(items),
        "lock_path": str(container.settings.skills_lock_path),
        "empty_copy": "暂无已登记 Skill",
        "note": "S0 只读：安装/启用/绑定在 S2 开放",
    }


@router.get("/skills/runs")
def skill_runs(
    skill_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    container: AppContainer = Depends(get_container),
    user=Depends(require(Permission.VIEW_AUDIT)),
) -> dict[str, Any]:
    runs = container.skill_runs.recent(limit * 2 if skill_id else limit)
    if skill_id:
        runs = [run for run in runs if run.skill_id == skill_id][:limit]
    return {
        "items": [_run_dict(run) for run in runs],
        "empty_copy": "暂无 Skill 运行记录",
    }


@router.get("/skills/{skill_id}")
def skill_detail(
    skill_id: str,
    container: AppContainer = Depends(get_container),
    user=Depends(require(Permission.VIEW_AUDIT)),
) -> dict[str, Any]:
    manifest = container.skill_catalog.get(skill_id)
    if manifest is None:
        raise DomainError("E008", f"Skill 不存在: {skill_id}", status_override=404)
    dynamic = container.skill_bindings.list_for_skill(skill_id)
    static = [b for b in container.skill_catalog.bindings() if b.skill_id == skill_id]
    installation = container.skill_installations.get(skill_id)
    runs = [run for run in container.skill_runs.recent(200) if run.skill_id == skill_id][:20]
    return {
        **manifest.to_dict(),
        "installation": installation.to_dict() if installation else None,
        "bindings": [
            {
                "platform": binding.platform,
                "shop_id": binding.shop_id,
                "enabled": binding.enabled,
                "priority": binding.priority,
                "credential_ref": getattr(binding, "credential_ref", ""),
            }
            for binding in (dynamic or static)
        ],
        "runs": [_run_dict(run) for run in runs],
    }


@router.post("/skills/{skill_id}/install")
def install_skill(
    skill_id: str,
    body: InstallRequest | None = None,
    container: AppContainer = Depends(get_container),
    user=Depends(require(Permission.VIEW_AUDIT)),
) -> dict[str, Any]:
    request = body or InstallRequest()
    if request.source == "package":
        if not request.package_path:
            raise DomainError("E006", "package 安装必须提供 package_path")
        installation = container.skill_lifecycle.install_package(
            skill_id, request.package_path, actor=user.username
        )
    else:
        installation = container.skill_lifecycle.install(skill_id, actor=user.username)
    _audit(container, user.username, "skill.install", skill_id, installation.to_dict())
    return {**installation.to_dict(), "note": "package 安装只落盘与校验，不自动执行包内脚本"}


@router.post("/skills/{skill_id}/verify")
def verify_skill(
    skill_id: str,
    container: AppContainer = Depends(get_container),
    user=Depends(require(Permission.VIEW_AUDIT)),
) -> dict[str, Any]:
    result = container.skill_lifecycle.verify(skill_id)
    _audit(container, user.username, "skill.verify", skill_id, result)
    return result


@router.post("/skills/{skill_id}/enable")
def enable_skill(
    skill_id: str,
    container: AppContainer = Depends(get_container),
    user=Depends(require(Permission.VIEW_AUDIT)),
) -> dict[str, Any]:
    installation = container.skill_lifecycle.set_enabled(skill_id, True, actor=user.username)
    _audit(container, user.username, "skill.enable", skill_id, installation.to_dict())
    return installation.to_dict()


@router.post("/skills/{skill_id}/disable")
def disable_skill(
    skill_id: str,
    container: AppContainer = Depends(get_container),
    user=Depends(require(Permission.VIEW_AUDIT)),
) -> dict[str, Any]:
    installation = container.skill_lifecycle.set_enabled(skill_id, False, actor=user.username)
    _audit(container, user.username, "skill.disable", skill_id, installation.to_dict())
    return installation.to_dict()


@router.get("/skills/{skill_id}/bindings")
def get_bindings(
    skill_id: str,
    container: AppContainer = Depends(get_container),
    user=Depends(require(Permission.VIEW_AUDIT)),
) -> dict[str, Any]:
    dynamic = container.skill_bindings.list_for_skill(skill_id)
    static = [b for b in container.skill_catalog.bindings() if b.skill_id == skill_id]
    items = dynamic or static
    return {
        "items": [
            {
                "platform": binding.platform,
                "shop_id": binding.shop_id,
                "enabled": binding.enabled,
                "priority": binding.priority,
                "credential_ref": getattr(binding, "credential_ref", ""),
            }
            for binding in items
        ],
        "note": "凭据只存引用；解析器按 platform + shop_id 匹配",
    }


@router.put("/skills/{skill_id}/bindings")
def put_binding(
    skill_id: str,
    body: BindingRequest,
    container: AppContainer = Depends(get_container),
    user=Depends(require(Permission.VIEW_AUDIT)),
) -> dict[str, Any]:
    binding = container.skill_lifecycle.set_binding(
        skill_id,
        platform=body.platform,
        shop_id=body.shop_id,
        enabled=body.enabled,
        priority=body.priority,
        credential_ref=body.credential_ref,
        config=body.config,
        actor=user.username,
    )
    _audit(
        container,
        user.username,
        "skill.bind",
        skill_id,
        {"platform": binding.platform, "shop_id": binding.shop_id, "enabled": binding.enabled},
    )
    return {
        "platform": binding.platform,
        "shop_id": binding.shop_id,
        "enabled": binding.enabled,
        "priority": binding.priority,
        "credential_ref": binding.credential_ref,
    }


@router.delete("/skills/{skill_id}/bindings")
def delete_binding(
    skill_id: str,
    platform: str = Query(default="*"),
    shop_id: str = Query(default="*"),
    container: AppContainer = Depends(get_container),
    user=Depends(require(Permission.VIEW_AUDIT)),
) -> dict[str, Any]:
    container.skill_lifecycle.remove_binding(skill_id, platform, shop_id)
    _audit(
        container,
        user.username,
        "skill.unbind",
        skill_id,
        {"platform": platform, "shop_id": shop_id},
    )
    return {"ok": True}
