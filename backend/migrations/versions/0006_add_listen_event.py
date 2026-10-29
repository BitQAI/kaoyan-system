"""0006_add_listen_event

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-30 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0006'
down_revision: Union[str, None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('listen_event',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('card_id', sa.Text(), nullable=False),
    sa.Column('ts', sa.Text(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('listen_event', schema=None) as batch_op:
        batch_op.create_index('idx_listen_event_card', ['card_id'], unique=False)
        batch_op.create_index('idx_listen_event_ts', ['ts'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('listen_event', schema=None) as batch_op:
        batch_op.drop_index('idx_listen_event_ts')
        batch_op.drop_index('idx_listen_event_card')

    op.drop_table('listen_event')
