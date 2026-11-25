"""demo 平台适配器：CSV fixture → RawPayload → CanonicalRecord。

日期占位符：fixture 里用 {D0}（窗口结束日）与 {D-1}（前一日），
适配器按请求窗口解析，保证任何一天运行都有确定性数据。
"""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from kernel.contexts.integration.domain.models import FetchChannelUnavailable, FetchSpec
from kernel.contexts.metric_data.domain.canonical_record import CanonicalRecord
from kernel.contexts.metric_data.domain.ports import RawPayload
from shared.types.values import Channel

DATASET_FILES = {
    "order": "orders.csv",
    "traffic": "traffic.csv",
    "ad": "ads.csv",
    "review": "reviews.csv",
    "inventory": "inventory.csv",
    "erp_inventory": "erp_inventory.csv",
    "wms_inventory": "wms_inventory.csv",
    "settlement": "settlement.csv",
}
NUMERIC_FIELDS = {
    "paid_amount",
    "refund_amount",
    "uv",
    "pv",
    "cost",
    "attributed_revenue",
    "dsr",
    "available",
    "rating",
    "settlement_amount",
    "commission",
}


class DemoPlatformAdapter:
    platform = "demo"

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.fixtures = Path(config.get("_module_dir", ".")) / "fixtures"

    # ------------------------------------------------------------------ fetch
    def fetch(self, spec: FetchSpec, channel: Channel) -> RawPayload:
        if channel is not Channel.BACKEND_EXPORT:
            raise FetchChannelUnavailable(f"demo 平台不提供 {channel.value} 通道")
        filename = DATASET_FILES.get(spec.dataset)
        if filename is None:
            raise FetchChannelUnavailable(f"demo 平台未提供数据集: {spec.dataset}")
        path = self.fixtures / filename
        if not path.is_file():
            raise FetchChannelUnavailable(f"导出文件不存在: {path}")

        rows: list[dict[str, Any]] = []
        with path.open(newline="", encoding="utf-8") as handle:
            for raw_row in csv.DictReader(handle):
                row = {
                    key: self._resolve_placeholders(value, spec.window.end)
                    for key, value in raw_row.items()
                }
                if "stat_date" in row and row["stat_date"]:
                    day = date.fromisoformat(str(row["stat_date"]))
                    if not spec.window.contains(day):
                        continue
                rows.append({k: self._coerce(k, v) for k, v in row.items()})
        digest = hashlib.sha256(
            json.dumps(rows, ensure_ascii=False, sort_keys=True, default=str).encode()
        ).hexdigest()
        return RawPayload(
            platform=spec.platform,
            shop_id=spec.shop_id,
            dataset=spec.dataset,
            channel=channel,
            records=rows,
            payload_hash=digest,
            storage_ref=path.name,
            meta={"source": "fixture", "empty_ok": True, "file": path.name},
        )

    # ------------------------------------------------------------------ canonical
    def to_canonical(self, raw: RawPayload) -> list[CanonicalRecord]:
        records: list[CanonicalRecord] = []
        for row in raw.records:
            dataset = raw.dataset
            if dataset == "order":
                key = str(row.get("order_id", ""))
            elif dataset == "settlement":
                key = str(row.get("order_id", ""))
            elif dataset == "review":
                key = str(row.get("review_id", ""))
            elif dataset in {"inventory", "erp_inventory", "wms_inventory"}:
                key = str(row.get("sku", ""))
            else:
                key = f"{raw.platform}:{raw.shop_id}:{row.get('stat_date', '')}"
            fields = dict(row)
            if dataset == "order":
                fields["buyer_phone"] = row.get("buyer_phone", "")
                fields["receiver_address"] = row.get("receiver_address", "")
            records.append(
                CanonicalRecord(
                    platform=raw.platform,
                    shop_id=raw.shop_id,
                    dataset=dataset,
                    business_key=key,
                    fields=fields,
                    raw_ref=raw.storage_ref,
                    status_enum=str(row.get("status")) if row.get("status") else None,
                    desensitized=False,
                )
            )
        return records

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _resolve_placeholders(value: Any, window_end: date) -> Any:
        if not isinstance(value, str):
            return value
        mapping = {
            "{D0}": window_end.isoformat(),
            "{D-1}": (window_end - timedelta(days=1)).isoformat(),
            "{D-2}": (window_end - timedelta(days=2)).isoformat(),
        }
        for token, replacement in mapping.items():
            value = value.replace(token, replacement)
        return value

    @staticmethod
    def _coerce(key: str, value: Any) -> Any:
        if value is None or value == "":
            return None
        if key in NUMERIC_FIELDS:
            try:
                return Decimal(str(value))
            except Exception:  # noqa: BLE001 - fixture 数据坏行留给数据合同校验
                return value
        return value
