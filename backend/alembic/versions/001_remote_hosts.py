"""add remote_hosts table

Revision ID: 001_remote_hosts
Revises: <previous_revision>
Create Date: 2026-04-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '001_remote_hosts'
down_revision = None  # ← remplacer par la dernière revision existante
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'remote_hosts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),

        # Identification
        sa.Column('name',     sa.String(255), nullable=False),
        sa.Column('protocol', sa.String(10),  nullable=False),
        sa.Column('host',     sa.String(255), nullable=False),
        sa.Column('port',     sa.Integer,     nullable=True),

        # Auth
        sa.Column('username',           sa.String(255), nullable=False),
        sa.Column('credential_type',    sa.String(30),  nullable=False),
        sa.Column('encrypted_password', sa.Text,        nullable=True),
        sa.Column('key_content',        sa.Text,        nullable=True),
        sa.Column('key_passphrase',     sa.Text,        nullable=True),
        sa.Column('domain',             sa.String(255), nullable=True),

        # WinRM
        sa.Column('winrm_transport',               sa.String(20), nullable=True, server_default='ntlm'),
        sa.Column('winrm_server_cert_validation',  sa.String(20), nullable=True, server_default='ignore'),

        # Metadata
        sa.Column('tags',           postgresql.JSON, nullable=True, server_default='[]'),
        sa.Column('os_info',        postgresql.JSON, nullable=True),
        sa.Column('notes',          sa.Text,         nullable=True),
        sa.Column('is_active',      sa.Boolean,      nullable=False, server_default='true'),
        sa.Column('last_connected', sa.DateTime,     nullable=True),
        sa.Column('created_at',     sa.DateTime,     nullable=False,
                  server_default=sa.func.now()),
        sa.Column('updated_at',     sa.DateTime,     nullable=False,
                  server_default=sa.func.now(), onupdate=sa.func.now()),

        # Unique constraint
        sa.UniqueConstraint('user_id', 'name', name='uq_remote_host_user_name'),
    )

    # Index pour les lookups par user + host/name
    op.create_index('ix_remote_hosts_user_id',   'remote_hosts', ['user_id'])
    op.create_index('ix_remote_hosts_protocol',  'remote_hosts', ['protocol'])
    op.create_index('ix_remote_hosts_host',      'remote_hosts', ['host'])


def downgrade() -> None:
    op.drop_index('ix_remote_hosts_host',     table_name='remote_hosts')
    op.drop_index('ix_remote_hosts_protocol', table_name='remote_hosts')
    op.drop_index('ix_remote_hosts_user_id',  table_name='remote_hosts')
    op.drop_table('remote_hosts')