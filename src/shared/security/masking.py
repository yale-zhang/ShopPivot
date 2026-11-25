"""脱敏与合规过滤（主文档表 3-32 / E-CMP-03 / D1）。

落点：DWD 入库前、日志落盘前、报表与导出、证据接口返回。
原文只允许 AUDIT 角色访问，且访问必须写审计。
"""
from __future__ import annotations

import re
from typing import Any, Final

MASK = "***"

# 默认脱敏字段清单：字段名 -> 掩码策略
SENSITIVE_FIELDS: Final[dict[str, str]] = {
    "buyer_nickname": "nickname",
    "buyer_nick": "nickname",
    "nickname": "nickname",
    "receiver_phone": "phone",
    "buyer_phone": "phone",
    "phone": "phone",
    "mobile": "phone",
    "receiver_address": "address",
    "address": "address",
    "order_remark": "remark",
    "buyer_message": "remark",
    "remark": "remark",
    "review_text": "text",
    "qa_text": "text",
    "im_content": "text",
    "logistics_no": "logistics",
    "waybill_no": "logistics",
}

# 导出默认不包含的列（含买家信息）
NON_EXPORTABLE_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "buyer_nickname",
        "buyer_nick",
        "receiver_phone",
        "receiver_address",
        "order_remark",
        "buyer_message",
        "im_content",
        "review_text",
        "qa_text",
    }
)

_PHONE_RE = re.compile(r"(?<!\d)(1[3-9]\d{9})(?!\d)")
_EMAIL_RE = re.compile(r"([A-Za-z0-9._%+-]{1,64})@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
_ID_RE = re.compile(r"(?<!\d)(\d{6})(\d{8})(\d{3}[\dXx])(?!\d)")


def mask_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) < 7:
        return MASK
    return f"{digits[:3]}{'*' * 4}{digits[-4:]}"


def mask_nickname(value: str) -> str:
    if not value:
        return value
    if len(value) <= 1:
        return MASK
    return f"{value[0]}{MASK}"


def mask_address(value: str) -> str:
    if not value:
        return value
    if len(value) <= 6:
        return MASK
    return f"{value[:6]}{'*' * 4}"


def mask_logistics(value: str) -> str:
    if len(value) <= 4:
        return MASK
    return f"{value[:2]}{'*' * 4}{value[-2:]}"


def mask_text(value: str) -> str:
    """对自由文本中的手机号 / 邮箱 / 身份证片段做掩码。"""
    if not value:
        return value
    masked = _PHONE_RE.sub(lambda m: mask_phone(m.group(1)), value)
    masked = _EMAIL_RE.sub(lambda m: f"{m.group(1)[:1]}{MASK}@{m.group(2)}", masked)
    masked = _ID_RE.sub(lambda m: f"{m.group(1)}{'*' * 8}{m.group(3)[-1]}", masked)
    return masked


def mask_value(field: str, value: Any) -> Any:
    if not isinstance(value, str) or not value:
        return value
    strategy = SENSITIVE_FIELDS.get(field.lower())
    if strategy is None:
        return mask_text(value)
    return {
        "nickname": mask_nickname,
        "phone": mask_phone,
        "address": mask_address,
        "logistics": mask_logistics,
        "remark": mask_text,
        "text": mask_text,
    }[strategy](value)


def mask_mapping(record: dict[str, Any]) -> dict[str, Any]:
    """返回脱敏副本，不修改入参。"""
    return {
        key: mask_value(key, value) if not isinstance(value, (dict, list)) else value
        for key, value in record.items()
    }


def redact_for_log(payload: Any) -> Any:
    """日志/异常详情脱敏：按键名掩码 + 对字符串做 PII 扫描。"""
    if isinstance(payload, dict):
        return {key: redact_for_log(mask_value(str(key), value)) for key, value in payload.items()}
    if isinstance(payload, list):
        return [redact_for_log(item) for item in payload]
    if isinstance(payload, str):
        return mask_text(payload)
    return payload
