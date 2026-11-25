"""模块装载服务：把模块 data 文件与声明真正落到 Kernel 资产。

Loading 阶段做四件事（全部幂等）：
1. 口径卡 YAML → metric_definition / metric_card；
2. DataContract → data_contract；
3. GateRule → gate_policy（只允许收紧，不允许放宽平台上限）；
4. ScenePackage.cron → schedule_plan。
Startup 后持久化 module_state 与启动报告，供 P09 展示阻断原因。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select

from kernel.contracts.extension_points import DataContractSpec, MetricCardFileSpec
from kernel.contracts.manifest_schema import ContributionKind, ModuleManifest
from kernel.contexts.metric_data.domain.metric_definition import MetricDefinition
from kernel.contexts.metric_data.domain.ports import MetricRepository
from kernel.persistence.base import Database, utcnow
from kernel.persistence.tables import (
    DataContractRow,
    GatePolicyRow,
    ModuleLoadReportRow,
    ModuleStateRow,
    SchedulePlanRow,
)
from shared.gate_level import GateLevel
from shared.types.values import Additivity, NullReason


class RuntimeModuleServices:
    def __init__(
        self,
        database: Database,
        metrics: MetricRepository,
        modules_dirs: list[Path],
    ) -> None:
        self.db = database
        self.metrics = metrics
        self.modules_dirs = modules_dirs
        self.gate_rules: dict[str, GateLevel] = {}

    # ------------------------------------------------------------------ loading
    def on_loading(self, manifest: ModuleManifest, contributions: list[Any]) -> None:
        module_dir = self._module_dir(manifest.name)
        for contribution in contributions:
            if contribution.kind is ContributionKind.METRIC_CARD:
                files = contribution.config.get("files", [])
                for rel in files:
                    self._load_metric_card(module_dir / rel, manifest)
            elif contribution.kind is ContributionKind.DATA_CONTRACT:
                self._upsert_contract(contribution.config, manifest)
            elif contribution.kind is ContributionKind.GATE_RULE:
                self._upsert_gate_rule(contribution.config, manifest)
            elif contribution.kind is ContributionKind.SCENE_PACKAGE:
                cron = contribution.config.get("cron")
                if cron:
                    self._upsert_schedule(contribution.config, manifest)

    def _load_metric_card(self, path: Path, manifest: ModuleManifest) -> None:
        if not path.is_file():
            raise FileNotFoundError(f"口径卡文件不存在: {path}")
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        spec = MetricCardFileSpec.model_validate(raw)
        try:
            null_policy = NullReason[spec.null_policy]
        except KeyError:
            null_policy = NullReason.NOT_APPLICABLE
        definition = MetricDefinition(
            metric_code=spec.metric_code,
            display_name=spec.display_name,
            version=spec.version,
            unit=spec.unit,
            precision=spec.precision,
            additivity=Additivity(spec.additivity),
            formula=spec.formula,
            null_policy=null_policy,
            denominator=spec.denominator,
            platform=spec.platform,
            source_mapping=spec.source_mapping,
            description=spec.description,
            concept_uri=spec.concept_uri,
            synonyms=tuple(spec.synonyms),
            probe_sql_template=spec.probe_sql_template,
            quality_tests=tuple(spec.quality_tests),
            display_order=spec.display_order,
            effective_from=spec.effective_from,
            breaking_change=spec.breaking_change,
        )
        card_payload = {
            "metric_code": spec.metric_code,
            "version": spec.version,
            "display_name": spec.display_name,
            "unit": spec.unit,
            "precision": spec.precision,
            "additivity": spec.additivity,
            "formula": spec.formula,
            "denominator": spec.denominator,
            "null_policy": spec.null_policy,
            "source_mapping": spec.source_mapping,
            "description": spec.description,
            "probe_sql_template": spec.probe_sql_template,
            "quality_tests": spec.quality_tests,
            "synonyms": spec.synonyms,
            "module": manifest.name,
            "module_version": manifest.version,
        }
        self.metrics.upsert_definition(definition, card_payload)

    def _upsert_contract(self, config: dict[str, Any], manifest: ModuleManifest) -> None:
        spec = DataContractSpec.model_validate(config)
        dataset = spec.dataset
        version = spec.version
        with self.db.session() as session:
            row = session.get(DataContractRow, (dataset, version))
            if row is None:
                row = DataContractRow(dataset=dataset, version=version)
                session.add(row)
            row.required_fields = spec.required_fields
            row.enum_sets = spec.enum_sets
            row.quality_tests = spec.quality_tests
            row.schema_def = {}
            row.platform = spec.platform

    def _upsert_gate_rule(self, config: dict[str, Any], manifest: ModuleManifest) -> None:
        action_code = str(config.get("action_code", ""))
        level = GateLevel.parse(config.get("gate_level", "L2"))
        if not action_code:
            raise ValueError(f"{manifest.name} 的 GateRule 缺少 action_code")
        self.gate_rules[action_code] = level
        with self.db.session() as session:
            row = session.execute(
                select(GatePolicyRow).where(
                    GatePolicyRow.action_code == action_code,
                    GatePolicyRow.version == str(config.get("version", "1")),
                )
            ).scalar_one_or_none()
            if row is None:
                session.add(
                    GatePolicyRow(
                        action_code=action_code,
                        gate_level=level.value,
                        version=str(config.get("version", "1")),
                        module=manifest.name,
                        signed_by=config.get("signed_by", ""),
                    )
                )
            else:
                row.gate_level = level.value
                row.module = manifest.name

    def _upsert_schedule(self, config: dict[str, Any], manifest: ModuleManifest) -> None:
        app_id = str(config.get("app_id", ""))
        if not app_id:
            return
        with self.db.session() as session:
            row = session.execute(
                select(SchedulePlanRow).where(SchedulePlanRow.app_id == app_id)
            ).scalar_one_or_none()
            if row is None:
                session.add(SchedulePlanRow(app_id=app_id, cron=str(config["cron"])))
            elif not row.degrade_switch:
                row.cron = str(config["cron"])
                row.enabled = True

    # ------------------------------------------------------------------ startup
    def on_startup(self, manifest: ModuleManifest) -> None:
        return None

    def persist_states(self, states: list[Any]) -> None:
        with self.db.session() as session:
            for state in states:
                row = session.get(ModuleStateRow, state.name)
                if row is None:
                    row = ModuleStateRow(name=state.name, version=state.version)
                    session.add(row)
                row.version = state.version
                row.category = (
                    state.category if isinstance(state.category, str) else state.category.value
                )
                row.state = state.state
                row.enabled = state.enabled
                row.contributions = list(state.contributions)
                row.blocking_reason = state.blocking_reason
                row.last_loaded_at = utcnow()
            session.add(
                ModuleLoadReportRow(
                    report={
                        "loaded": [s.name for s in states if s.state == "INSTALLED"],
                        "states": [
                            {
                                "name": s.name,
                                "state": s.state,
                                "reason": s.blocking_reason,
                            }
                            for s in states
                        ],
                    }
                )
            )

    # ------------------------------------------------------------------ helpers
    def _module_dir(self, name: str) -> Path:
        for root in self.modules_dirs:
            candidate = root / name
            if candidate.is_dir():
                return candidate
        raise FileNotFoundError(f"找不到模块目录: {name}")
