"""Trusted execution ownership and durable conservative call accounting."""
from alembic import op
import sqlalchemy as sa

revision = '0005_job_execution'
down_revision = '0004_feature_licenses'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('jobs') as batch:
        batch.add_column(sa.Column('auth_session_id', sa.Uuid(), nullable=True))
        batch.create_foreign_key('fk_jobs_auth_session', 'sessions', ['auth_session_id'], ['id'], ondelete='SET NULL')
        batch.add_column(sa.Column('auth_session_version', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('active_attempt_id', sa.Uuid(), nullable=True))
        batch.add_column(sa.Column('lease_expires_at', sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'))
        batch.add_column(sa.Column('cancel_requested', sa.Boolean(), nullable=False, server_default=sa.false()))
        for name in ('checkpoint', 'call_counts', 'cost_policy'):
            batch.add_column(sa.Column(name, sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
        batch.create_check_constraint('ck_job_attempt_count', 'attempt_count BETWEEN 0 AND 3')
    with op.batch_alter_table('usage_ledger') as batch:
        batch.add_column(sa.Column('operation_id', sa.String(128), nullable=True))
        batch.create_unique_constraint('uq_usage_ledger_operation_id', ['operation_id'])


def downgrade():
    with op.batch_alter_table('usage_ledger') as batch:
        batch.drop_constraint('uq_usage_ledger_operation_id', type_='unique')
        batch.drop_column('operation_id')
    with op.batch_alter_table('jobs') as batch:
        batch.drop_constraint('ck_job_attempt_count', type_='check')
        batch.drop_constraint('fk_jobs_auth_session', type_='foreignkey')
        for name in ('auth_session_id', 'auth_session_version', 'active_attempt_id', 'lease_expires_at',
                     'attempt_count', 'cancel_requested', 'checkpoint', 'call_counts', 'cost_policy'):
            batch.drop_column(name)
