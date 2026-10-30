"""0007_add_card_payload

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-30 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0007'
down_revision: Union[str, None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('card', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'payload', sa.Text(), nullable=False, server_default='{}'))


def downgrade() -> None:
    with op.batch_alter_table('card', schema=None) as batch_op:
        batch_op.drop_column('payload')
