"""add release diagnosis fields

Revision ID: add_release_diagnosis_fields
Revises: remove_version_column
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_release_diagnosis_fields'
down_revision = 'remove_version_column'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 添加发布诊断相关字段
    op.add_column('release_records', sa.Column('failure_diagnosis', sa.JSON(), nullable=True))
    op.add_column('release_records', sa.Column('deployment_conditions', sa.JSON(), nullable=True))
    op.add_column('release_records', sa.Column('events', sa.JSON(), nullable=True))


def downgrade() -> None:
    # 移除字段
    op.drop_column('release_records', 'failure_diagnosis')
    op.drop_column('release_records', 'deployment_conditions')
    op.drop_column('release_records', 'events')
