"""add manager role and approval flow

Revision ID: c7d4a2b18e35
Revises: a3f8c2d91b04
Create Date: 2026-03-26 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c7d4a2b18e35'
down_revision: Union[str, None] = 'a3f8c2d91b04'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostgreSQL 12+ allows ALTER TYPE ADD VALUE inside a transaction
    # as long as the new value is not used in the same transaction.
    op.execute(sa.text("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'manager'"))
    op.execute(sa.text("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'pending_approval'"))
    op.add_column(
        'restaurants',
        sa.Column('requires_approval', sa.Boolean(), nullable=False, server_default='false'),
    )


def downgrade() -> None:
    # PostgreSQL does not support removing enum values — leave them in place.
    op.drop_column('restaurants', 'requires_approval')
