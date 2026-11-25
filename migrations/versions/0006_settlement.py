"""S09 对账表：dwd_settlement / settlement_diff。

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-25
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from kernel.persistence import tables  # noqa: F401
from kernel.persistence.base import Base

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

_TABLES = ["dwd_settlement", "settlement_diff"]


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    pending = [
        table
        for table in Base.metadata.sorted_tables
        if table.name in _TABLES and table.name not in existing
    ]
    if pending:
        Base.metadata.create_all(bind, tables=pending)


def downgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    for table in reversed([name for name in _TABLES if name in existing]):
        op.drop_table(table)
