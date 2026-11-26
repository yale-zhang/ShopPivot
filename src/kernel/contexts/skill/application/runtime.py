"""SkillRuntime：能力路由、信任/风险校验、执行、运行记录。"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from kernel.contexts.integration.domain.sourcing import ProviderUnavailable
from kernel.contexts.skill.domain.models import (
    SkillInvocation,
    SkillManifest,
    SkillOutput,
    SkillRisk,
    SkillRun,
    SkillUnavailable,
    TrustLevel,
)
from kernel.contexts.skill.domain.ports import SkillCatalogPort, SkillRunRepository
from kernel.contexts.skill.infrastructure.runners import CliSkillRunner
from shared.errors.registry import DomainError


class SkillRuntime:
    def __init__(
        self,
        catalog: SkillCatalogPort,
        runs: SkillRunRepository,
        *,
        settings: Any = None,
        runner: CliSkillRunner | None = None,
        installations: Any = None,
        bindings: Any = None,
    ) -> None:
        self.catalog = catalog
        self.runs = runs
        self.settings = settings
        self.runner = runner or CliSkillRunner()
        self.installations = installations
        self.bindings = bindings

    def execute(
        self,
        capability: str,
        payload: dict[str, Any],
        *,
        scene: str,
        platform: str,
        shop_id: str,
        run_id: str = "",
        requested_by: str = "system",
    ) -> SkillOutput:
        match = self.catalog.find(capability, platform, shop_id)
        if match is None:
            raise SkillUnavailable(f"没有可用的 Skill 能力: {capability}")
        manifest, binding = match
        if self.installations is not None:
            installation = self.installations.get(manifest.id)
            if installation is not None and installation.status in {"DISABLED", "FAILED"}:
                raise SkillUnavailable(f"Skill 已停用/失败: {manifest.id}")
        if self.bindings is not None:
            dynamic = self.bindings.get(manifest.id, platform, shop_id)
            if dynamic is not None:
                if not dynamic.enabled:
                    raise SkillUnavailable(f"Skill 绑定已停用: {manifest.id}")
                binding = dynamic
        risk = manifest.capability(capability)
        if risk is None:
            raise SkillUnavailable(f"Skill {manifest.id} 未声明能力: {capability}")
        if risk.risk is SkillRisk.L3:
            raise SkillUnavailable("支付/财务能力禁止自动化（L3）")
        ceiling = getattr(getattr(self.settings, "platform_gate_max", None), "rank", 2)
        if risk.risk.rank > ceiling:
            raise SkillUnavailable(
                f"Skill 能力 {capability} 需要 {risk.risk.value}，超过平台上限"
            )
        if manifest.trust is TrustLevel.UNTRUSTED:
            raise SkillUnavailable(f"Skill {manifest.id} 未通过信任校验")
        if manifest.trust is TrustLevel.COMMUNITY and risk.risk is not SkillRisk.L0:
            raise SkillUnavailable("社区 Skill 只能执行只读能力")

        module_name, class_name = manifest.adapter.split(":", 1)
        try:
            from kernel.runtime.factories import import_object

            adapter_cls = import_object(manifest.adapter)
        except Exception as exc:  # noqa: BLE001
            raise SkillUnavailable(f"Skill 适配器不可用 {module_name}:{class_name}: {exc}") from exc
        invocation = SkillInvocation(
            manifest=manifest,
            binding=binding,
            platform=platform,
            shop_id=shop_id,
            run_id=run_id,
            capability=capability,
            requested_by=requested_by,
            settings=self.settings,
        )
        started = perf_counter()
        try:
            output: SkillOutput = adapter_cls().execute(invocation, payload)
        except ProviderUnavailable as exc:
            latency = int((perf_counter() - started) * 1000)
            self._record(manifest, capability, scene, platform, shop_id, run_id, "FAILED", payload, None, latency, "E008")
            raise SkillUnavailable(str(exc)) from exc
        except DomainError:
            raise
        except Exception as exc:  # noqa: BLE001
            latency = int((perf_counter() - started) * 1000)
            self._record(manifest, capability, scene, platform, shop_id, run_id, "FAILED", payload, None, latency, "E008")
            raise SkillUnavailable(f"Skill 执行失败: {exc}") from exc
        latency = int((perf_counter() - started) * 1000)
        self._record(
            manifest,
            capability,
            scene,
            platform,
            shop_id,
            run_id,
            output.status,
            payload,
            output,
            latency,
            output.error_code,
        )
        return output

    def _record(
        self,
        manifest: SkillManifest,
        capability: str,
        scene: str,
        platform: str,
        shop_id: str,
        run_id: str,
        status: str,
        payload: dict[str, Any],
        output: SkillOutput | None,
        latency_ms: int,
        error_code: str | None,
    ) -> None:
        self.runs.record(
            SkillRun(
                run_id=run_id,
                skill_id=manifest.id,
                skill_version=manifest.version,
                capability=capability,
                scene=scene,
                platform=platform,
                shop_id=shop_id,
                status=status,
                input_digest=_digest(payload),
                output_digest=_digest(output.data if output else None),
                latency_ms=latency_ms,
                error_code=error_code,
                created_at=datetime.now(UTC),
            )
        )


def _digest(value: Any) -> str:
    try:
        raw = json.dumps(value, ensure_ascii=False, default=str, sort_keys=True)
    except (TypeError, ValueError):
        raw = str(value)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
