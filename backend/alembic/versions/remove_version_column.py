"""remove version column from release_records

Revision ID: remove_version_column
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'remove_version_column'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 移除 release_records 表的 version 列
    op.drop_column('release_records', 'version')


def downgrade() -> None:
    # 恢复 version 列
    op.add_column('release_records', sa.Column('version', sa.String(length=64), nullable=False))
