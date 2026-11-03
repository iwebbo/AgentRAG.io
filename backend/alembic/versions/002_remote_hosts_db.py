"""remote_hosts: add db_type, db_name, db_options (protocols psrp + db)

Revision ID: 002_remote_hosts_db
Revises: 001_remote_hosts
Create Date: 2026-11-02
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '002_remote_hosts_db'
down_revision = '001_remote_hosts'   # ← adapter si 001 n'est pas le head actuel
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('remote_hosts', sa.Column('db_type',    sa.String(20),  nullable=True))
    op.add_column('remote_hosts', sa.Column('db_name',    sa.String(128), nullable=True))
    op.add_column('remote_hosts', sa.Column('db_options', postgresql.JSON, nullable=True))


def downgrade() -> None:
    op.drop_column('remote_hosts', 'db_options')
    op.drop_column('remote_hosts', 'db_name')
    op.drop_column('remote_hosts', 'db_type')