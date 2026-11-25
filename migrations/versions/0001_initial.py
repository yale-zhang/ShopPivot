"""M0 初始 schema（以 Kernel 统一数据模型为基线）。

Revision ID: 0001
Revises:
Create Date: 2026-11-25

说明：本版用 metadata.create_all 建基线（表结构以 kernel/persistence/tables.py 为准），
后续增量迁移用 `alembic revision --autogenerate` 生成显式 DDL。
"""
from __future__ import annotations

from alembic import op

from kernel.persistence.base import Base
from kernel.persistence import tables  # noqa: F401  确保所有表已注册

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

_AUDIT_FN = """
CREATE OR REPLACE FUNCTION shoppivot_audit_immutable() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is append-only';
END;
$$ LANGUAGE plpgsql;
"""

_AUDIT_TRIGGER = """
DROP TRIGGER IF EXISTS trg_audit_log_immutable ON audit_log;
CREATE TRIGGER trg_audit_log_immutable
BEFORE UPDATE OR DELETE ON audit_log
FOR EACH ROW EXECUTE FUNCTION shoppivot_audit_immutable();
"""


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind)
    if bind.dialect.name == "postgresql":
        op.execute(_AUDIT_FN)
        op.execute(_AUDIT_TRIGGER)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS trg_audit_log_immutable ON audit_log;")
        op.execute("DROP FUNCTION IF EXISTS shoppivot_audit_immutable();")
    Base.metadata.drop_all(bind)
