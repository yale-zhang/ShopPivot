"""脱敏领域服务（表 3-32 / E-CMP-03）。"""
from __future__ import annotations

from typing import Any, Sequence

from kernel.contexts.metric_data.domain.canonical_record import CanonicalRecord
from shared.security.masking import mask_mapping, mask_value, redact_for_log

AUDIT_ROLES = frozenset({"OWNER"})


class Desensitizer:
    """列表/报表/日志默认脱敏；原文只允许审计角色访问且必须留访问日志。"""

    def mask_fields(self, fields: dict[str, Any]) -> dict[str, Any]:
        return mask_mapping(fields)

    def mask_record(self, record: CanonicalRecord) -> CanonicalRecord:
        if record.desensitized:
            return record
        return CanonicalRecord(
            platform=record.platform,
            shop_id=record.shop_id,
            dataset=record.dataset,
            business_key=record.business_key,
            fields=self.mask_fields(record.fields),
            raw_ref=record.raw_ref,
            status_enum=record.status_enum,
            desensitized=True,
        )

    def mask_records(self, records: Sequence[CanonicalRecord]) -> list[CanonicalRecord]:
        return [self.mask_record(record) for record in records]

    def mask_log(self, payload: Any) -> Any:
        return redact_for_log(payload)

    @staticmethod
    def can_view_raw(role: str) -> bool:
        return role.upper() in AUDIT_ROLES

    def display(self, field: str, value: Any) -> Any:
        return mask_value(field, value)
