"""order items

Revision ID: 7cf1544802de
Revises: 87d74e391545
Create Date: 2026-10-07 12:21:27.914044

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7cf1544802de'
down_revision: Union[str, Sequence[str], None] = '87d74e391545'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("orders", "resource_ids", new_column_name="items")


def downgrade() -> None:
    op.alter_column("orders", "items", new_column_name="resource_ids")
