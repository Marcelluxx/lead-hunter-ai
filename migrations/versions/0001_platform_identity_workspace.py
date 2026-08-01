"""Create identity, workspace, job, cost and audit boundaries."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_platform_identity_workspace"
down_revision = None
branch_labels = None
depends_on = None


UUID = sa.Uuid()
UTC_NOW = sa.text("CURRENT_TIMESTAMP")


def _id_column() -> sa.Column:
    return sa.Column("id", UUID, primary_key=True, nullable=False)


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=UTC_NOW),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=UTC_NOW),
    )


def upgrade() -> None:
    op.create_table(
        "users",
        _id_column(),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_platform_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("session_version", sa.Integer(), nullable=False, server_default="1"),
        *_timestamps(),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "workspaces",
        _id_column(),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_timestamps(),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "sessions",
        _id_column(),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("refresh_token_hash", sa.String(64), nullable=False),
        sa.Column("csrf_token_hash", sa.String(64), nullable=False),
        sa.Column("mfa_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=UTC_NOW),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=UTC_NOW),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_sessions_user_active", "sessions", ["user_id", "revoked_at"])
    op.create_table(
        "mfa_credentials",
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("secret_ciphertext", sa.Text(), nullable=False),
        sa.Column("recovery_code_hashes", sa.JSON(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        *_timestamps(),
    )
    op.create_table(
        "oidc_identities",
        _id_column(),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("provider", "subject"),
    )
    op.create_table(
        "workspace_memberships",
        _id_column(),
        sa.Column("workspace_id", UUID, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("role IN ('admin','operator','viewer')", name="ck_membership_role"),
        sa.UniqueConstraint("workspace_id", "user_id"),
    )
    op.create_table(
        "provider_credentials",
        _id_column(),
        sa.Column("workspace_id", UUID, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("ciphertext", sa.Text(), nullable=False),
        sa.Column("key_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("fingerprint", sa.String(32), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("workspace_id", "provider"),
    )
    op.create_table(
        "jobs",
        _id_column(),
        sa.Column("workspace_id", UUID, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("kind", sa.String(80), nullable=False),
        sa.Column("state", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("estimated_cost", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("result_ref", sa.String(500)),
        sa.Column("error_code", sa.String(100)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.CheckConstraint(
            "state IN ('queued','validating','running','completed','partial','cancelled','failed')",
            name="ck_job_state",
        ),
        sa.CheckConstraint("estimated_cost >= 0", name="ck_job_cost_nonnegative"),
        sa.UniqueConstraint("workspace_id", "idempotency_key"),
    )
    op.create_index("ix_jobs_workspace_state", "jobs", ["workspace_id", "state"])
    op.create_table(
        "job_attempts",
        _id_column(),
        sa.Column("job_id", UUID, sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.String(200)),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=UTC_NOW),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False, server_default=UTC_NOW),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(100)),
        sa.UniqueConstraint("job_id", "attempt_number"),
    )
    op.create_table(
        "usage_budgets",
        _id_column(),
        sa.Column("workspace_id", UUID, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="EUR"),
        sa.Column("hard_limit", sa.Numeric(18, 6), nullable=False),
        sa.Column("spent", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("reserved", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("warning_threshold", sa.Numeric(5, 4), nullable=False, server_default="0.8"),
        *_timestamps(),
        sa.CheckConstraint("hard_limit >= 0", name="ck_budget_limit_nonnegative"),
        sa.CheckConstraint("spent >= 0", name="ck_budget_spent_nonnegative"),
        sa.CheckConstraint("reserved >= 0", name="ck_budget_reserved_nonnegative"),
        sa.CheckConstraint("warning_threshold > 0 AND warning_threshold < 1", name="ck_budget_warning_threshold"),
        sa.UniqueConstraint("workspace_id"),
    )
    op.create_table(
        "usage_reservations",
        _id_column(),
        sa.Column("workspace_id", UUID, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("budget_id", UUID, sa.ForeignKey("usage_budgets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", UUID, sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount", sa.Numeric(18, 6), nullable=False),
        sa.Column("settled_amount", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("state", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=UTC_NOW),
        sa.Column("settled_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("state IN ('active','settled','released')", name="ck_reservation_state"),
        sa.CheckConstraint("amount >= 0", name="ck_reservation_amount_nonnegative"),
        sa.CheckConstraint("settled_amount >= 0", name="ck_reservation_settled_nonnegative"),
        sa.UniqueConstraint("job_id"),
    )
    op.create_table(
        "usage_ledger",
        _id_column(),
        sa.Column("workspace_id", UUID, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", UUID, sa.ForeignKey("jobs.id", ondelete="SET NULL")),
        sa.Column("entry_type", sa.String(20), nullable=False),
        sa.Column("amount", sa.Numeric(18, 6), nullable=False),
        sa.Column("provider", sa.String(80)),
        sa.Column("units", sa.Numeric(18, 6)),
        sa.Column("reason", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=UTC_NOW),
        sa.CheckConstraint("entry_type IN ('reservation','charge','release','override')", name="ck_ledger_entry_type"),
    )
    op.create_index("ix_usage_ledger_workspace_created", "usage_ledger", ["workspace_id", "created_at"])
    op.create_table(
        "audit_events",
        _id_column(),
        sa.Column("workspace_id", UUID, sa.ForeignKey("workspaces.id", ondelete="SET NULL")),
        sa.Column("actor_user_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("target_type", sa.String(80)),
        sa.Column("target_id", sa.String(100)),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("correlation_id", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=UTC_NOW),
    )
    op.create_index("ix_audit_workspace_created", "audit_events", ["workspace_id", "created_at"])

    if op.get_bind().dialect.name == "postgresql":
        _enable_postgres_rls()
        op.execute(
            "DO $$ BEGIN "
            "IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'leadhunter_app') THEN "
            "GRANT USAGE ON SCHEMA public TO leadhunter_app; "
            "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO leadhunter_app; "
            "END IF; "
            "IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'leadhunter_worker') THEN "
            "GRANT USAGE ON SCHEMA public TO leadhunter_worker; "
            "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO leadhunter_worker; "
            "END IF; END $$"
        )
        op.execute(
            "CREATE OR REPLACE FUNCTION public.app_job_workspace(p_job_id uuid) "
            "RETURNS uuid LANGUAGE sql SECURITY DEFINER "
            "SET search_path = pg_catalog, public AS $$ "
            "SELECT workspace_id FROM public.jobs WHERE id = p_job_id $$"
        )
        op.execute("REVOKE ALL ON FUNCTION public.app_job_workspace(uuid) FROM PUBLIC")
        op.execute(
            "DO $$ BEGIN "
            "IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'leadhunter_worker') THEN "
            "GRANT EXECUTE ON FUNCTION public.app_job_workspace(uuid) TO leadhunter_worker; "
            "END IF; END $$"
        )


def _enable_postgres_rls() -> None:
    direct_tables = (
        "provider_credentials",
        "jobs",
        "usage_budgets",
        "usage_reservations",
        "usage_ledger",
    )
    predicate = "workspace_id = NULLIF(current_setting('app.workspace_id', true), '')::uuid"
    for table in direct_tables:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
        op.execute(
            f'CREATE POLICY "{table}_workspace_isolation" ON "{table}" '
            f"USING ({predicate}) WITH CHECK ({predicate})"
        )
    op.execute('ALTER TABLE "audit_events" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "audit_events" FORCE ROW LEVEL SECURITY')
    op.execute(
        'CREATE POLICY "audit_events_workspace_read" ON "audit_events" FOR SELECT '
        f"USING ({predicate})"
    )
    op.execute(
        'CREATE POLICY "audit_events_scoped_insert" ON "audit_events" FOR INSERT '
        f"WITH CHECK (workspace_id IS NULL OR {predicate})"
    )
    op.execute('ALTER TABLE "job_attempts" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "job_attempts" FORCE ROW LEVEL SECURITY')
    op.execute(
        'CREATE POLICY "job_attempts_workspace_isolation" ON "job_attempts" '
        "USING (EXISTS (SELECT 1 FROM jobs WHERE jobs.id = job_attempts.job_id)) "
        "WITH CHECK (EXISTS (SELECT 1 FROM jobs WHERE jobs.id = job_attempts.job_id))"
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP FUNCTION IF EXISTS public.app_job_workspace(uuid)")
    op.drop_index("ix_audit_workspace_created", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_usage_ledger_workspace_created", table_name="usage_ledger")
    op.drop_table("usage_ledger")
    op.drop_table("usage_reservations")
    op.drop_table("usage_budgets")
    op.drop_table("job_attempts")
    op.drop_index("ix_jobs_workspace_state", table_name="jobs")
    op.drop_table("jobs")
    op.drop_table("provider_credentials")
    op.drop_table("workspace_memberships")
    op.drop_table("oidc_identities")
    op.drop_table("mfa_credentials")
    op.drop_index("ix_sessions_user_active", table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("workspaces")
    op.drop_table("users")
