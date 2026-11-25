"""只读探针执行器：白名单表 + 参数化 SELECT，绝不直连外部平台库。"""
from __future__ import annotations

import re
from typing import Any

from sqlalchemy import text

from kernel.persistence.base import Database
from shared.errors.registry import DomainError

_ALLOWED_TABLES = {
    "dws_daily_metric",
    "dwd_order",
    "dwd_traffic",
    "dwd_ad",
    "dwd_review",
    "report",
    "metric_definition",
}
_TABLE_RE = re.compile(r"\b(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_]*)", re.IGNORECASE)
_WRITE_RE = re.compile(r"\b(insert|update|delete|drop|alter|create|grant|truncate)\b", re.I)


class SqlProbeRunner:
    def __init__(self, database: Database) -> None:
        self.db = database

    def run(self, sql_template: str, params: dict[str, Any]) -> Any:
        self._assert_readonly(sql_template)
        with self.db.session() as session:
            row = session.execute(text(sql_template), params).first()
            return row[0] if row else None

    @staticmethod
    def _assert_readonly(sql: str) -> None:
        stripped = sql.strip()
        if not stripped.lower().startswith("select"):
            raise DomainError("E006", "探针只允许 SELECT")
        if ";" in stripped:
            raise DomainError("E006", "探针只允许单条语句")
        if _WRITE_RE.search(stripped):
            raise DomainError("E006", "探针包含写操作关键字")
        tables = {match.group(1).lower() for match in _TABLE_RE.finditer(stripped)}
        if not tables:
            raise DomainError("E006", "探针未引用任何表")
        illegal = tables - _ALLOWED_TABLES
        if illegal:
            raise DomainError("E006", f"探针引用了非白名单表: {', '.join(sorted(illegal))}")
