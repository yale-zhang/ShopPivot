"""M2 写入闸门表：write_plan / write_execution / write_token。

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-25
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from kernel.persistence import tables  # noqa: F401  注册完整 metadata
from kernel.persistence.base import Base

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

_M2_TABLES = ["write_plan", "write_execution", "write_token"]


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    pending = [
        table
        for table in Base.metadata.sorted_tables
        if table.name in _M2_TABLES and table.name not in existing
    ]
    if pending:
        Base.metadata.create_all(bind, tables=pending)


def downgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    for table in reversed([name for name in _M2_TABLES if name in existing]):
        op.drop_table(table)
