"""Add task fields

Revision ID: 001
Create Date: 2024-01-10 16:15:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic
revision = '001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # 添加新列
    op.add_column('tasks', sa.Column('error_details', sa.JSON(), nullable=True))
    op.add_column('tasks', sa.Column('task_metadata', sa.JSON(), nullable=True))
    op.add_column('tasks', sa.Column('result', sa.JSON(), nullable=True))
    op.add_column('tasks', sa.Column('system_info', sa.JSON(), nullable=True))

def downgrade():
    # 删除新添加的列
    op.drop_column('tasks', 'system_info')
    op.drop_column('tasks', 'result')
    op.drop_column('tasks', 'task_metadata')
    op.drop_column('tasks', 'error_details') 