"""guest users

Revision ID: 4d2f7a91c3be
Revises: 8b23f849fdc5
Create Date: 2026-11-03 12:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '4d2f7a91c3be'
down_revision: Union[str, Sequence[str], None] = '8b23f849fdc5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('users', 'password_hash', existing_type=sa.String(length=255), nullable=True)
    op.add_column('users', sa.Column('is_guest', sa.Boolean(), server_default=sa.text('false'), nullable=False))


def downgrade() -> None:
    # Guests with no orders are disposable. Guests with orders keep their purchases but get an unusable hash
    # (no password verifies against it); they recover through the M-Pesa code flow on the new version.
    op.execute("DELETE FROM users WHERE password_hash IS NULL AND NOT EXISTS (SELECT 1 FROM orders WHERE orders.user_id = users.id)")
    op.execute("UPDATE users SET password_hash = '!locked' WHERE password_hash IS NULL")
    op.drop_column('users', 'is_guest')
    op.alter_column('users', 'password_hash', existing_type=sa.String(length=255), nullable=False)
