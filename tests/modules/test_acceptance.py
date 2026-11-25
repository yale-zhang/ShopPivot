"""M0 模块化验收 A/B/C（主文档表 9-23）。

A：装第二个模块不改 Kernel 代码；
B：循环依赖 / api_compat 不匹配 / data 漏登记 均在启动期阻断并给模块名；
C：声明 gate_level_max=L2 在平台上限 L0 下被拒；禁用 mod_daily_report 后无残留贡献。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from kernel.contracts.manifest_schema import ModuleManifest
from kernel.module_loader import ModuleLoader
from kernel.registry import ExtensionPointRegistry
from shared.gate_level import GateLevel

ROOT = Path(__file__).resolve().parents[2]
REAL_MODULES = ROOT / "modules"


def write_module(root: Path, name: str, manifest_source: str, *, data: dict[str, str] | None = None) -> None:
    module_dir = root / name
    (module_dir / "data" / "metric_cards").mkdir(parents=True, exist_ok=True)
    (module_dir / "manifest.py").write_text(manifest_source, encoding="utf-8")
    for rel, content in (data or {}).items():
        target = module_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def loader(dirs: list[Path], *, disabled: set[str] | None = None) -> tuple[ModuleLoader, object]:
    registry = ExtensionPointRegistry()
    instance = ModuleLoader(
        dirs,
        registry=registry,
        kernel_api="1.0",
        platform_gate_max=GateLevel.L0_READ_ONLY,
        credential_scopes={"pdd:report:read", "demo:report:read"},
        disabled_modules=disabled or set(),
    )
    report = instance.run()
    return instance, report


def test_acceptance_a_second_module_without_kernel_change(tmp_path: Path) -> None:
    write_module(
        tmp_path,
        "mod_probe_card",
        '''
from kernel.contracts.manifest_schema import Contribution, ContributionKind, ModuleManifest

manifest = ModuleManifest(
    name="mod_probe_card",
    version="1.0.0",
    category="business",
    depends=["mod_core"],
    provides=[
        Contribution(
            kind=ContributionKind.WORKBENCH_CARD,
            id="card.probe",
            config={"card_id": "card.probe", "page_id": "P09", "title": "探针卡片"},
        )
    ],
    data=[],
)
''',
    )
    instance, report = loader([REAL_MODULES, tmp_path])
    assert "mod_probe_card" in report.loaded
    assert instance.registry.get("WorkbenchCard", "card.probe") is not None
    cards = [c.id for c in instance.registry.by_kind("WorkbenchCard")]
    assert "card.daily_report" in cards and "card.probe" in cards

    disabled_instance, disabled_report = loader(
        [REAL_MODULES, tmp_path], disabled={"mod_probe_card"}
    )
    assert "mod_probe_card" not in disabled_report.loaded
    assert disabled_instance.registry.get("WorkbenchCard", "card.probe") is None
    assert disabled_report.state_of("mod_probe_card").state == "DISABLED"


def test_acceptance_b_cycle_is_blocked_globally(tmp_path: Path) -> None:
    write_module(
        tmp_path,
        "mod_cycle_a",
        'from kernel.contracts.manifest_schema import ModuleManifest\n'
        'manifest = ModuleManifest(name="mod_cycle_a", version="1.0.0", category="business",'
        ' depends=["mod_cycle_b"], data=[])\n',
    )
    write_module(
        tmp_path,
        "mod_cycle_b",
        'from kernel.contracts.manifest_schema import ModuleManifest\n'
        'manifest = ModuleManifest(name="mod_cycle_b", version="1.0.0", category="business",'
        ' depends=["mod_cycle_a"], data=[])\n',
    )
    instance, report = loader([tmp_path])
    assert report.global_failure is True
    assert report.loaded == []
    blocked = {issue.module for issue in report.blocked}
    assert {"mod_cycle_a", "mod_cycle_b"} <= blocked
    assert all("循环依赖" in issue.message for issue in report.blocked)


def test_acceptance_b_api_compat_mismatch_blocks_only_that_module(tmp_path: Path) -> None:
    write_module(
        tmp_path,
        "mod_bad_api",
        'from kernel.contracts.manifest_schema import ModuleManifest\n'
        'manifest = ModuleManifest(name="mod_bad_api", version="1.0.0", category="business",'
        ' api_compat=">=9.0,<10.0", data=[])\n',
    )
    _, report = loader([tmp_path])
    issue = next(issue for issue in report.blocked if issue.module == "mod_bad_api")
    assert issue.check == "M03"
    assert "api_compat" in issue.message


def test_acceptance_b_missing_data_file_blocks(tmp_path: Path) -> None:
    write_module(
        tmp_path,
        "mod_missing_data",
        'from kernel.contracts.manifest_schema import ModuleManifest\n'
        'manifest = ModuleManifest(name="mod_missing_data", version="1.0.0", category="business",'
        ' data=["data/metric_cards/missing.yaml"])\n',
    )
    _, report = loader([tmp_path])
    issue = next(issue for issue in report.blocked if issue.module == "mod_missing_data")
    assert issue.check == "M06"
    assert "data 文件不存在" in issue.message


def test_acceptance_c_l2_declaration_rejected_at_platform_ceiling_l0(tmp_path: Path) -> None:
    write_module(
        tmp_path,
        "mod_l2_writer",
        'from kernel.contracts.manifest_schema import ModuleManifest\n'
        'manifest = ModuleManifest(name="mod_l2_writer", version="1.0.0", category="business",'
        ' gate_level_max="L2", data=[])\n',
    )
    _, report = loader([tmp_path])
    issue = next(issue for issue in report.blocked if issue.module == "mod_l2_writer")
    assert issue.check == "M04"
    assert "gate_level_max=L2" in issue.message
    assert "L0" in issue.message
    assert report.loaded == []


def test_acceptance_c_disabling_daily_report_leaves_no_contribution(tmp_path: Path) -> None:
    instance, report = loader([REAL_MODULES], disabled={"mod_daily_report"})
    state = report.state_of("mod_daily_report")
    assert state is not None and state.state == "DISABLED"
    assert "mod_daily_report" not in report.loaded

    scene_ids = {c.config.get("scene") for c in instance.registry.by_kind("ScenePackage")}
    assert "S01" not in scene_ids
    card_ids = {c.id for c in instance.registry.by_kind("WorkbenchCard")}
    assert "card.daily_report" not in card_ids
    assert "card.metric_alert" not in card_ids
    metric_contribs = {c.id for c in instance.registry.by_kind("MetricCard")}
    assert "metrics.daily" not in metric_contribs


@pytest.mark.parametrize(
    "field",
    ["gate_level_max", "requires", "api_compat"],
)
def test_manifest_declares_security_and_compat_fields(field: str) -> None:
    manifest = ModuleManifest(
        name="mod_fields",
        version="1.0.0",
        category="business",
        depends=["mod_core"],
        data=[],
    )
    assert hasattr(manifest, field)
