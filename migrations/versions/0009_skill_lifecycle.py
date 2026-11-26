"""S2a 技能生命周期：skill_installation / skill_binding。

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-26
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from kernel.persistence import tables  # noqa: F401
from kernel.persistence.base import Base

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

_TABLES = ["skill_installation", "skill_binding"]


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
