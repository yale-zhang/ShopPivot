"""生成/刷新契约 JSON Schema（docs/contracts/*.schema.json）。

契约测试会比较生成结果与仓库快照，schema 变更必须显式提交并升 api_compat。
"""
from __future__ import annotations

import json
from pathlib import Path

from kernel.contracts.extension_points import DataContractSpec, MetricCardFileSpec
from kernel.contracts.manifest_schema import ModuleManifest
from kernel.contracts.worker_api import (
    CallbackRequest,
    CapabilitiesResponse,
    ErrorEnvelope,
    HeartbeatRequest,
    JobQueryResponse,
    JobStartRequest,
    JobStartResponse,
    SuggestRequest,
    SuggestResponse,
    WriteRequest,
    WriteResponse,
)

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS = ROOT / "docs" / "contracts"


def _dump(models: list[type], title: str, path: Path) -> None:
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": title,
        "kernel_api": "1.0",
        "types": {model.__name__: model.model_json_schema() for model in models},
    }
    path.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    CONTRACTS.mkdir(parents=True, exist_ok=True)
    _dump(
        [
            JobStartRequest,
            JobStartResponse,
            JobQueryResponse,
            SuggestRequest,
            SuggestResponse,
            WriteRequest,
            WriteResponse,
            CallbackRequest,
            HeartbeatRequest,
            CapabilitiesResponse,
            ErrorEnvelope,
        ],
        "Worker API 契约（kernel api 1.0）",
        CONTRACTS / "worker_api.schema.json",
    )
    _dump(
        [MetricCardFileSpec],
        "MetricCard 口径卡契约（data/metric_cards/*.yaml）",
        CONTRACTS / "metric_card.schema.json",
    )
    _dump(
        [DataContractSpec],
        "DataContract 数据合同契约（模块 provides）",
        CONTRACTS / "data_contract.schema.json",
    )
    _dump(
        [ModuleManifest],
        "ModuleManifest 契约（modules/*/manifest.py）",
        CONTRACTS / "module_manifest.schema.json",
    )
    print("schemas written to", CONTRACTS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
