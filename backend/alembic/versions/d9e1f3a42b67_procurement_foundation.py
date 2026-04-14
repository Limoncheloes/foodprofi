"""procurement foundation

Revision ID: d9e1f3a42b67
Revises: c7d4a2b18e35
Create Date: 2026-04-14 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'd9e1f3a42b67'
down_revision: Union[str, None] = 'c7d4a2b18e35'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ALTER TYPE ADD VALUE must run outside a transaction in PostgreSQL.
    connection = op.get_bind()
    connection.execute(sa.text("COMMIT"))
    connection.execute(sa.text("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'curator'"))
    connection.execute(sa.text("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'routing'"))
    connection.execute(sa.text("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'received'"))
    connection.execute(sa.text("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'closed'"))
    result = connection.execute(sa.text(
        "SELECT 1 FROM pg_type WHERE typname = 'procurementitemstatus'"
    ))
    if result.fetchone() is None:
        connection.execute(sa.text(
            "CREATE TYPE procurementitemstatus AS ENUM "
            "('pending_curator', 'assigned', 'purchased', 'not_found', 'substituted')"
        ))
    connection.execute(sa.text("BEGIN"))

    op.add_column(
        'categories',
        sa.Column('default_buyer_id', sa.UUID(), nullable=True)
    )
    op.create_foreign_key(
        'fk_categories_default_buyer',
        'categories', 'users',
        ['default_buyer_id'], ['id'],
        ondelete='SET NULL'
    )

    op.create_table(
        'procurement_items',
        sa.Column('id', sa.UUID(), nullable=False, primary_key=True),
        sa.Column('order_id', sa.UUID(), nullable=False),
        sa.Column('catalog_item_id', sa.UUID(), nullable=True),
        sa.Column('raw_name', sa.String(255), nullable=True),
        sa.Column('quantity_ordered', sa.Numeric(10, 3), nullable=False),
        sa.Column('quantity_received', sa.Numeric(10, 3), nullable=True),
        sa.Column('unit', sa.String(50), nullable=False),
        sa.Column(
            'status',
            postgresql.ENUM('pending_curator', 'assigned', 'purchased', 'not_found', 'substituted',
                            name='procurementitemstatus', create_type=False),
            nullable=False,
            server_default='pending_curator',
        ),
        sa.Column('buyer_id', sa.UUID(), nullable=True),
        sa.Column('category_id', sa.UUID(), nullable=True),
        sa.Column('curator_note', sa.Text(), nullable=True),
        sa.Column('substitution_note', sa.Text(), nullable=True),
        sa.Column('is_catalog_item', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['catalog_item_id'], ['catalog_items.id']),
        sa.ForeignKeyConstraint(['buyer_id'], ['users.id']),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id']),
        sa.CheckConstraint(
            'catalog_item_id IS NOT NULL OR raw_name IS NOT NULL',
            name='ck_procurement_item_has_name'
        ),
        sa.CheckConstraint('quantity_ordered > 0', name='ck_procurement_item_qty_positive'),
    )

    op.create_table(
        'routing_rules',
        sa.Column('id', sa.UUID(), nullable=False, primary_key=True),
        sa.Column('keyword', sa.String(255), nullable=False),
        sa.Column('buyer_id', sa.UUID(), nullable=False),
        sa.Column('category_id', sa.UUID(), nullable=True),
        sa.Column('created_by_curator', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['buyer_id'], ['users.id']),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id']),
        sa.ForeignKeyConstraint(['created_by_curator'], ['users.id']),
        sa.UniqueConstraint('keyword', name='uq_routing_rules_keyword'),
    )


def downgrade() -> None:
    op.drop_table('routing_rules')
    op.drop_table('procurement_items')
    op.drop_constraint('fk_categories_default_buyer', 'categories', type_='foreignkey')
    op.drop_column('categories', 'default_buyer_id')
    connection = op.get_bind()
    connection.execute(sa.text("DROP TYPE IF EXISTS procurementitemstatus"))
    # PostgreSQL does not support removing enum values from userrole/orderstatus
