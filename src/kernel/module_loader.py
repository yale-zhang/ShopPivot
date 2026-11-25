"""ModuleLoader：Discovery → Resolution → Loading → Mounting → Startup（主文档表 9-16）。

设计取舍：
- 装配在启动期一次完成，不做运行时热装载；
- 禁用通过持久化 module_state + 查询期过滤贡献实现，"禁用后无残留"仍可验证；
- 单个模块被拒绝不拖垮整体，只有依赖环导致整体回滚（表 9-14 第 02 行）。
"""
from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Protocol

from packaging.specifiers import SpecifierSet

from kernel.contracts.manifest_schema import (
    ALL_CONTRIBUTION_KINDS,
    ContributionKind,
    ManifestIssue,
    ModuleCategory,
    ModuleManifest,
    validate_data_order,
)
from kernel.registry import DuplicateContribution, ExtensionPointRegistry
from kernel.runtime.factories import import_object
from shared.gate_level import GateLevel


class ModuleLoadServices(Protocol):
    """由 bootstrap 容器实现：落库口径卡/权限/数据合同、持久化模块状态。"""

    def on_loading(self, manifest: ModuleManifest, contributions: list[Any]) -> None: ...  # noqa: E704

    def on_startup(self, manifest: ModuleManifest) -> None: ...  # noqa: E704

    def persist_states(self, states: list["ModuleStateView"]) -> None: ...  # noqa: E704


@dataclass(frozen=True)
class ModuleStateView:
    name: str
    version: str
    category: str
    state: str
    enabled: bool
    contributions: list[dict[str, str]] = field(default_factory=list)
    depends: list[str] = field(default_factory=list)
    blocking_reason: str | None = None


@dataclass
class ModuleStartupReport:
    loaded: list[str] = field(default_factory=list)
    blocked: list[ManifestIssue] = field(default_factory=list)
    degraded: list[ManifestIssue] = field(default_factory=list)
    disabled: list[str] = field(default_factory=list)
    states: list[ModuleStateView] = field(default_factory=list)
    contribution_count: int = 0
    global_failure: bool = False
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "loaded": self.loaded,
            "blocked": [
                {"module": i.module, "check": i.check, "reason": i.message} for i in self.blocked
            ],
            "degraded": [
                {"module": i.module, "check": i.check, "reason": i.message} for i in self.degraded
            ],
            "disabled": self.disabled,
            "states": [
                {
                    "name": s.name,
                    "version": s.version,
                    "category": s.category,
                    "state": s.state,
                    "enabled": s.enabled,
                    "contributions": s.contributions,
                    "depends": s.depends,
                    "blocking_reason": s.blocking_reason,
                }
                for s in self.states
            ],
            "contribution_count": self.contribution_count,
            "global_failure": self.global_failure,
            "generated_at": self.generated_at.isoformat(),
        }

    def state_of(self, module: str) -> ModuleStateView | None:
        return next((s for s in self.states if s.name == module), None)


@dataclass
class _Discovered:
    manifest: ModuleManifest
    directory: Path


def _import_manifest(path: Path, unique: str) -> ModuleManifest:
    spec = importlib.util.spec_from_file_location(f"_shoppivot_manifest_{unique}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载 manifest: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    raw = getattr(module, "manifest", None)
    if raw is None:
        raise AttributeError(f"{path} 未导出 manifest 对象")
    if callable(raw) and not isinstance(raw, ModuleManifest):
        raw = raw()
    if isinstance(raw, ModuleManifest):
        return raw
    return ModuleManifest.model_validate(raw)


class ModuleLoader:
    def __init__(
        self,
        modules_dirs: Iterable[Path | str],
        *,
        registry: ExtensionPointRegistry | None = None,
        kernel_api: str = "1.0",
        platform_gate_max: GateLevel = GateLevel.L0_READ_ONLY,
        credential_scopes: Iterable[str] = (),
        disabled_modules: Iterable[str] = (),
        services: ModuleLoadServices | None = None,
    ) -> None:
        self.modules_dirs = [Path(p) for p in modules_dirs]
        self.registry = registry if registry is not None else ExtensionPointRegistry()
        self.kernel_api = kernel_api
        self.platform_gate_max = platform_gate_max
        self.credential_scopes = set(credential_scopes)
        self.disabled_modules = set(disabled_modules)
        self.services = services
        self._dirs: dict[str, Path] = {}
        self._order: list[str] = []
        self._cycle_detected = False

    # ------------------------------------------------------------------ discovery
    def discover(self) -> tuple[dict[str, _Discovered], list[ManifestIssue]]:
        discovered: dict[str, _Discovered] = {}
        issues: list[ManifestIssue] = []
        seen_paths: set[Path] = set()
        for directory in self.modules_dirs:
            if not directory.is_dir():
                issues.append(ManifestIssue("M00", str(directory), f"模块目录不存在: {directory}", True))
                continue
            for manifest_path in sorted(directory.glob("*/manifest.py")):
                if manifest_path.parent.name.startswith("_"):
                    continue  # _template 等脚手架不参与装配
                if manifest_path in seen_paths:
                    continue
                seen_paths.add(manifest_path)
                module_dir = manifest_path.parent
                try:
                    manifest = _import_manifest(manifest_path, f"{len(seen_paths)}_{module_dir.name}")
                except Exception as exc:  # noqa: BLE001 - 装配期必须收集所有错误
                    issues.append(
                        ManifestIssue(
                            "M01", module_dir.name, f"manifest 无法解析: {exc}", fatal=True
                        )
                    )
                    continue
                if manifest.name in discovered:
                    issues.append(
                        ManifestIssue(
                            "M01",
                            manifest.name,
                            f"模块名重复: {manifest.name}（{module_dir}）",
                            fatal=True,
                        )
                    )
                    continue
                if module_dir.name != manifest.name:
                    issues.append(
                        ManifestIssue(
                            "M01",
                            manifest.name,
                            f"目录名 {module_dir.name} 与 manifest.name {manifest.name} 不一致",
                            fatal=True,
                        )
                    )
                    continue
                discovered[manifest.name] = _Discovered(manifest, module_dir)
                self._dirs[manifest.name] = module_dir
        return discovered, issues

    # ------------------------------------------------------------------ resolution
    def _sort(self, manifests: dict[str, ModuleManifest]) -> tuple[list[str], list[str]]:
        """Kahn 拓扑排序；返回 (order, cycle_nodes)。"""
        indegree = {name: 0 for name in manifests}
        children: dict[str, list[str]] = {name: [] for name in manifests}
        for name, manifest in manifests.items():
            for dep in manifest.depends:
                if dep in manifests:
                    indegree[name] += 1
                    children[dep].append(name)
        ready = sorted(name for name, degree in indegree.items() if degree == 0)
        order: list[str] = []
        while ready:
            current = ready.pop(0)
            order.append(current)
            for child in sorted(children[current]):
                indegree[child] -= 1
                if indegree[child] == 0:
                    ready.append(child)
            ready.sort()
        cycle_nodes = sorted(name for name, degree in indegree.items() if degree > 0)
        return order, cycle_nodes

    def _check_manifest(
        self,
        manifest: ModuleManifest,
        discovered: dict[str, _Discovered],
        capabilities: set[str],
        contracts: set[tuple[str, str]],
    ) -> list[ManifestIssue]:
        issues: list[ManifestIssue] = []

        if manifest.category is ModuleCategory.BUNDLE and manifest.provides:
            issues.append(ManifestIssue("M01", manifest.name, "bundle 不得包含 provides", True))

        for dep in manifest.depends:
            if dep not in discovered:
                issues.append(
                    ManifestIssue("M02", manifest.name, f"依赖模块不存在: {dep}", True)
                )
            elif not discovered[dep].manifest.enabled:
                issues.append(
                    ManifestIssue("M02", manifest.name, f"依赖模块已被禁用: {dep}", True)
                )

        if not SpecifierSet(manifest.api_compat).contains(self.kernel_api):
            issues.append(
                ManifestIssue(
                    "M03",
                    manifest.name,
                    f"api_compat {manifest.api_compat} 与 Kernel {self.kernel_api} 不匹配",
                    True,
                )
            )

        if not manifest.gate_level_max.at_most(self.platform_gate_max):
            issues.append(
                ManifestIssue(
                    "M04",
                    manifest.name,
                    f"模块 {manifest.name} 未加载：声明 gate_level_max={manifest.gate_level_max.value}"
                    f" 超出平台当前上限 {self.platform_gate_max.value}",
                    True,
                )
            )

        missing_caps = manifest.requirement_capabilities() - capabilities
        if missing_caps:
            issues.append(
                ManifestIssue(
                    "M05",
                    manifest.name,
                    f"requires 能力不可达: {', '.join(sorted(missing_caps))}（缺对应 Worker）",
                    True,
                )
            )
        missing_scopes = manifest.requirement_scopes() - self.credential_scopes
        if missing_scopes:
            issues.append(
                ManifestIssue(
                    "M05",
                    manifest.name,
                    f"requires 凭据范围未授权: {', '.join(sorted(missing_scopes))}",
                    True,
                )
            )
        missing_contracts = manifest.requirement_contracts() - contracts
        if missing_contracts:
            issues.append(
                ManifestIssue(
                    "M05",
                    manifest.name,
                    "requires 数据合同不存在: "
                    + ", ".join(f"{dataset}@{version}" for dataset, version in sorted(missing_contracts)),
                    True,
                )
            )

        module_dir = self._dirs[manifest.name]
        for rel in manifest.data:
            if not (module_dir / rel).is_file():
                issues.append(
                    ManifestIssue("M06", manifest.name, f"data 文件不存在: {rel}", True)
                )
        issues.extend(validate_data_order(manifest.name, manifest.data))

        for contribution in manifest.provides:
            if contribution.kind.value not in ALL_CONTRIBUTION_KINDS:
                issues.append(
                    ManifestIssue(
                        "M07",
                        manifest.name,
                        f"未知扩展点类型: {contribution.kind.value}",
                        True,
                    )
                )
            factory = contribution.config.get("factory")
            if factory and contribution.kind in {
                ContributionKind.SCENE_PACKAGE,
                ContributionKind.PLATFORM_ADAPTER,
                ContributionKind.WRITE_ACTION,
                ContributionKind.HEALTH_CHECK,
                ContributionKind.WORKER_CAPABILITY,
            }:
                try:
                    import_object(factory)
                except Exception as exc:  # noqa: BLE001
                    issues.append(
                        ManifestIssue(
                            "M07",
                            manifest.name,
                            f"贡献 {contribution.id} 的工厂无法导入: {exc}",
                            True,
                        )
                    )

        hooks = manifest.hooks
        for hook in (hooks.on_install, hooks.on_upgrade, hooks.on_uninstall, hooks.on_startup):
            if hook:
                try:
                    import_object(hook)
                except Exception as exc:  # noqa: BLE001
                    issues.append(
                        ManifestIssue("M08", manifest.name, f"hook 无法导入: {hook} ({exc})", True)
                    )
        return issues

    def resolve(
        self, discovered: dict[str, _Discovered], discovery_issues: list[ManifestIssue]
    ) -> tuple[list[str], list[ManifestIssue]]:
        manifests = {name: item.manifest for name, item in discovered.items()}
        issues = list(discovery_issues)
        order, cycle_nodes = self._sort(manifests)
        if cycle_nodes:
            self._cycle_detected = True
            cycle = " -> ".join(cycle_nodes + [cycle_nodes[0]])
            for name in cycle_nodes:
                issues.append(
                    ManifestIssue("M02", name, f"检测到循环依赖，整体拒绝装配: {cycle}", True)
                )
            return [], issues

        capabilities: set[str] = set()
        contracts: set[tuple[str, str]] = set()
        for manifest in manifests.values():
            if not manifest.enabled or manifest.name in self.disabled_modules:
                continue
            if not SpecifierSet(manifest.api_compat).contains(self.kernel_api):
                continue
            for contribution in manifest.provides:
                if contribution.kind is ContributionKind.WORKER_CAPABILITY:
                    capabilities.add(str(contribution.config.get("capability", contribution.id)))
                if contribution.kind is ContributionKind.DATA_CONTRACT:
                    contracts.add(
                        (
                            str(contribution.config.get("dataset", contribution.id)),
                            str(contribution.config.get("version", "1")),
                        )
                    )

        blocked: dict[str, list[ManifestIssue]] = {}
        for name, item in discovered.items():
            manifest = item.manifest
            if not manifest.enabled or name in self.disabled_modules:
                continue
            module_issues = self._check_manifest(manifest, discovered, capabilities, contracts)
            if module_issues:
                blocked[name] = [i for i in module_issues if i.fatal] or module_issues
                issues.extend(module_issues)

        # 依赖被拒绝的模块连带拒绝，直到稳定
        changed = True
        while changed:
            changed = False
            for name, item in discovered.items():
                if name in blocked or name in self.disabled_modules:
                    continue
                for dep in item.manifest.depends:
                    if dep in blocked:
                        issue = ManifestIssue(
                            "M02", name, f"依赖模块 {dep} 未加载，连带拒绝", True
                        )
                        blocked[name] = [issue]
                        issues.append(issue)
                        changed = True
                        break

        ordered = [
            name
            for name in order
            if name not in blocked
            and name not in self.disabled_modules
            and discovered[name].manifest.enabled
        ]
        self._order = ordered
        return ordered, issues

    # ------------------------------------------------------------------ loading
    def load(self, ordered: list[str], discovered: dict[str, _Discovered]) -> list[ManifestIssue]:
        issues: list[ManifestIssue] = []
        self.registry.snapshot()
        for name in ordered:
            manifest = discovered[name].manifest
            try:
                for contribution in manifest.provides:
                    self.registry.register(
                        manifest.name,
                        contribution.kind.value,
                        contribution.id,
                        contribution.config,
                    )
            except DuplicateContribution as exc:
                self.registry.unregister_module(manifest.name)
                issues.append(ManifestIssue("M07", name, str(exc), True))
                continue
            if self.services is not None:
                try:
                    self.services.on_loading(manifest, manifest.provides)
                except Exception as exc:  # noqa: BLE001
                    self.registry.unregister_module(manifest.name)
                    issues.append(
                        ManifestIssue("M07", name, f"模块数据装载失败: {exc}", True)
                    )
        return issues

    # ------------------------------------------------------------------ startup
    def startup(
        self, ordered: list[str], discovered: dict[str, _Discovered]
    ) -> list[ManifestIssue]:
        issues: list[ManifestIssue] = []
        for name in ordered:
            manifest = discovered[name].manifest
            try:
                if self.services is not None:
                    self.services.on_startup(manifest)
                if manifest.hooks.on_startup:
                    import_object(manifest.hooks.on_startup)()
            except Exception as exc:  # noqa: BLE001 - 启动失败降级，不阻断整体
                issues.append(ManifestIssue("M08", name, f"on_startup 失败: {exc}", False))
                continue
            for contribution in manifest.provides:
                if contribution.kind is not ContributionKind.HEALTH_CHECK:
                    continue
                factory = contribution.config.get("factory")
                if not factory:
                    continue
                try:
                    checker = import_object(factory)
                    result = checker() if callable(checker) else checker.check()
                    ok, message = result if isinstance(result, tuple) else (bool(result), "")
                except Exception as exc:  # noqa: BLE001
                    ok, message = False, str(exc)
                if not ok:
                    issues.append(
                        ManifestIssue("M08", name, f"健康检查未通过: {message or contribution.id}", False)
                    )
        return issues

    # ------------------------------------------------------------------ orchestration
    def run(self, *, validate_only: bool = False) -> ModuleStartupReport:
        discovered, discovery_issues = self.discover()
        ordered, resolution_issues = self.resolve(discovered, discovery_issues)
        report = ModuleStartupReport()
        fatal = [i for i in resolution_issues if i.fatal]
        report.blocked = fatal
        report.global_failure = self._cycle_detected

        for name, item in discovered.items():
            if not item.manifest.enabled or name in self.disabled_modules:
                report.disabled.append(name)

        loading_issues: list[ManifestIssue] = []
        startup_issues: list[ManifestIssue] = []
        if ordered and not report.global_failure:
            if not validate_only:
                loading_issues = self.load(ordered, discovered)
                report.blocked.extend([i for i in loading_issues if i.fatal])
                loaded = [n for n in ordered if n not in {i.module for i in loading_issues}]
                startup_issues = self.startup(loaded, discovered)
                report.degraded = startup_issues
            else:
                loaded = ordered
        else:
            loaded = []

        degraded_names = {i.module for i in startup_issues}
        blocked_names = {i.module for i in report.blocked}
        report.loaded = sorted(loaded)
        for name, item in discovered.items():
            manifest = item.manifest
            if name in blocked_names:
                state = "REJECTED"
                reason = next(
                    (i.message for i in report.blocked if i.module == name), "装配被拒绝"
                )
            elif name in report.disabled:
                state = "DISABLED"
                reason = "manifest.enabled=False 或被持久化禁用"
            elif name in degraded_names:
                state = "DEGRADED"
                reason = next(
                    (i.message for i in startup_issues if i.module == name), "启动检查未通过"
                )
            elif name in loaded:
                state = "INSTALLED"
                reason = None
            else:
                state = "REJECTED"
                reason = "未进入装配顺序"
            report.states.append(
                ModuleStateView(
                    name=name,
                    version=manifest.version,
                    category=manifest.category.value,
                    state=state,
                    enabled=manifest.enabled and name not in self.disabled_modules,
                    contributions=[
                        {"kind": c.kind.value, "id": c.id} for c in manifest.provides
                    ],
                    depends=list(manifest.depends),
                    blocking_reason=reason,
                )
            )
        report.contribution_count = len(self.registry)
        if not validate_only and self.services is not None:
            self.services.persist_states(report.states)
        return report

    @property
    def order(self) -> list[str]:
        return list(self._order)
