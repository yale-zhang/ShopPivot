"""拼多多平台适配器：字段映射 + 状态枚举 + 三级取数前两级。"""
from __future__ import annotations

import csv
import hashlib
import json
import os
from decimal import Decimal
from pathlib import Path
from typing import Any

from kernel.contexts.integration.domain.models import FetchChannelUnavailable, FetchSpec
from kernel.contexts.metric_data.domain.canonical_record import CanonicalRecord
from kernel.contexts.metric_data.domain.ports import RawPayload
from shared.types.values import Channel

# 平台字段 → 统一数据模型字段（表 9-7「字段适配」）
FIELD_MAP: dict[str, dict[str, str]] = {
    "order": {
        "date": "stat_date",
        "order_sn": "order_id",
        "pay_amount": "paid_amount",
        "refund_amount": "refund_amount",
        "order_status": "status",
        "buyer_nick": "buyer_nickname",
        "buyer_phone": "buyer_phone",
        "receiver_address": "receiver_address",
        "goods_id": "sku",
    },
    "traffic": {"date": "stat_date", "visitor_count": "uv", "page_views": "pv"},
    "ad": {"date": "stat_date", "plan_name": "campaign", "spend": "cost", "gmv": "attributed_revenue"},
    "review": {"review_id": "review_id", "score": "rating", "content": "content"},
    "inventory": {"goods_id": "sku", "quantity": "available"},
}

# 平台状态 → 统一状态（禁止把平台原始状态直接写进报表）
STATUS_MAP: dict[str, str] = {
    "1": "PAID",
    "2": "REFUNDED",
    "3": "PAID",
    "4": "CLOSED",
    "PAID": "PAID",
    "REFUNDED": "REFUNDED",
}

NUMERIC_FIELDS = {
    "paid_amount",
    "refund_amount",
    "uv",
    "pv",
    "cost",
    "attributed_revenue",
    "available",
    "rating",
}


class PddPlatformAdapter:
    platform = "pdd"

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.export_dir = Path(config.get("_export_dir", "./storage/exports"))

    # ------------------------------------------------------------------ fetch
    def fetch(self, spec: FetchSpec, channel: Channel) -> RawPayload:
        if channel is Channel.OPEN_API:
            self._assert_openapi_ready()
            raise FetchChannelUnavailable("OpenAPI 客户端待店铺授权联调后启用（M2）")
        if channel is not Channel.BACKEND_EXPORT:
            raise FetchChannelUnavailable("pdd 适配器 M0 不提供该通道")
        path = self.export_dir / f"pdd_{spec.dataset}.csv"
        if not path.is_file():
            raise FetchChannelUnavailable(
                f"未找到后台导出文件: {path}（请先在商家后台导出并放入受控目录）"
            )
        rows = [
            {k: self._coerce(k, v) for k, v in raw.items()}
            for raw in csv.DictReader(path.read_text(encoding="utf-8-sig").splitlines())
        ]
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
            meta={"source": "backend_export", "empty_ok": True, "file": str(path)},
        )

    def _assert_openapi_ready(self) -> None:
        required = ("PDD_CLIENT_ID", "PDD_CLIENT_SECRET", "PDD_ACCESS_TOKEN")
        missing = [name for name in required if not os.environ.get(name)]
        if missing:
            raise FetchChannelUnavailable(
                "拼多多 OpenAPI 凭据缺失（" + ", ".join(missing) + "），fail-closed 不补数"
            )

    # ------------------------------------------------------------------ canonical
    def to_canonical(self, raw: RawPayload) -> list[CanonicalRecord]:
        field_map = FIELD_MAP.get(raw.dataset, {})
        records: list[CanonicalRecord] = []
        for row in raw.records:
            mapped: dict[str, Any] = {}
            for source, value in row.items():
                mapped[field_map.get(source, source)] = value
            if raw.dataset == "order" and "stat_date" not in mapped:
                mapped["stat_date"] = None
            status = mapped.get("status")
            canonical_status = STATUS_MAP.get(str(status), str(status)) if status else None
            mapped["status"] = canonical_status
            key = str(
                mapped.get("order_id")
                or mapped.get("review_id")
                or mapped.get("sku")
                or f"{raw.platform}:{raw.shop_id}:{mapped.get('stat_date', '')}"
            )
            records.append(
                CanonicalRecord(
                    platform=raw.platform,
                    shop_id=raw.shop_id,
                    dataset=raw.dataset,
                    business_key=key,
                    fields=mapped,
                    raw_ref=raw.storage_ref,
                    status_enum=canonical_status,
                    desensitized=False,
                )
            )
        return records

    @staticmethod
    def _coerce(key: str, value: Any) -> Any:
        if value is None or value == "":
            return None
        if key in NUMERIC_FIELDS:
            try:
                return Decimal(str(value))
            except Exception:  # noqa: BLE001
                return value
        return value
