"""ModuleManifest 规范测试（表 9-13 / 表 9-14 的输入侧）。"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from kernel.contracts.manifest_schema import (
    Contribution,
    ContributionKind,
    ModuleCategory,
    ModuleManifest,
    validate_data_order,
)


def _manifest(**kwargs):  # type: ignore[no-untyped-def]
    base = dict(
        name="mod_sample",
        version="1.0.0",
        category=ModuleCategory.BUSINESS,
        depends=["mod_core"],
        provides=[
            Contribution(
                kind=ContributionKind.WORKBENCH_CARD,
                id="card.sample",
                config={"card_id": "card.sample", "page_id": "P09"},
            )
        ],
    )
    base.update(kwargs)
    return ModuleManifest(**base)


def test_valid_manifest_defaults() -> None:
    manifest = _manifest()
    assert manifest.api_compat == ">=1.0,<2.0"
    assert manifest.gate_level_max.value == "L0"
    assert manifest.config_namespace == "modules.mod_sample"
    assert manifest.table_prefix


def test_invalid_module_name_rejected() -> None:
    for name in ["sample", "mod-Bad", "bundle"]:
        with pytest.raises(ValidationError):
            _manifest(name=name)


def test_l3_cannot_be_gate_ceiling() -> None:
    with pytest.raises(ValidationError):
        _manifest(gate_level_max="L3")


def test_bundle_must_only_declare_depends() -> None:
    with pytest.raises(ValidationError):
        _manifest(name="bundle_demo", category=ModuleCategory.BUNDLE, depends=[])
    with pytest.raises(ValidationError):
        _manifest(name="bundle_demo", category=ModuleCategory.BUNDLE)


def test_core_requires_contributions() -> None:
    with pytest.raises(ValidationError):
        _manifest(category=ModuleCategory.CORE, provides=[])


def test_api_compat_and_scene_formats() -> None:
    with pytest.raises(ValidationError):
        _manifest(api_compat="not-a-range")
    with pytest.raises(ValidationError):
        _manifest(scenes=["S1"])


def test_contribution_id_must_be_stable_lowercase() -> None:
    with pytest.raises(ValidationError):
        Contribution(kind=ContributionKind.WORKBENCH_CARD, id="S01")


def test_data_order_detects_wrong_sequence_and_unknown_partition() -> None:
    issues = validate_data_order(
        "mod_x",
        ["data/metric_cards/a.yaml", "security/permissions.csv"],
    )
    assert issues and issues[0].check == "M06"
    unknown = validate_data_order("mod_x", ["random/file.txt"])
    assert unknown and "未登记" in unknown[0].message


def test_requirement_helpers() -> None:
    manifest = _manifest(
        requires=[
            {"kind": "capability", "name": "EXPORT_PARSE"},
            {"kind": "credential_scope", "scope": "pdd:report:read"},
            {"kind": "data_contract", "dataset": "pdd.order.daily", "version": "1"},
        ]
    )
    assert manifest.requirement_capabilities() == {"EXPORT_PARSE"}
    assert manifest.requirement_scopes() == {"pdd:report:read"}
    assert manifest.requirement_contracts() == {("pdd.order.daily", "1")}
