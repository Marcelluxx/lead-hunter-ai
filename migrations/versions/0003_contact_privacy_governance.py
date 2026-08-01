"""Add typed contacts, privacy policy, suppression and data-subject requests."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_contact_privacy_governance"
down_revision = "0002_discovery_provenance"
branch_labels = None
depends_on = None

UUID = sa.Uuid()
UTC_NOW = sa.text("CURRENT_TIMESTAMP")


def _id() -> sa.Column:
    return sa.Column("id", UUID, primary_key=True, nullable=False)


def upgrade() -> None:
    op.create_table(
        "workspace_privacy_policies",
        sa.Column("workspace_id", UUID, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("purpose", sa.String(500), nullable=False),
        sa.Column("legal_basis", sa.String(500), nullable=False),
        sa.Column("privacy_contact", sa.String(320), nullable=False),
        sa.Column("market", sa.String(20), nullable=False, server_default="IT_EU"),
        sa.Column("named_contact_retention_days", sa.Integer(), nullable=False, server_default="90"),
        sa.Column("policy_version", sa.String(80), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_by", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=UTC_NOW),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=UTC_NOW),
        sa.CheckConstraint("market = 'IT_EU'", name="ck_privacy_policy_market"),
        sa.CheckConstraint("named_contact_retention_days BETWEEN 1 AND 90", name="ck_privacy_policy_named_retention"),
    )
    op.create_table(
        "suppression_entries",
        _id(),
        sa.Column("workspace_id", UUID, sa.ForeignKey("workspaces.id", ondelete="CASCADE")),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("scope_key", sa.String(36), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("reason", sa.String(80), nullable=False),
        sa.Column("created_by", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=UTC_NOW),
        sa.CheckConstraint("kind IN ('email','phone')", name="ck_suppression_kind"),
        sa.CheckConstraint("scope IN ('workspace','global')", name="ck_suppression_scope"),
        sa.UniqueConstraint("scope_key", "kind", "fingerprint"),
    )
    op.create_index("ix_suppression_lookup", "suppression_entries", ["kind", "fingerprint", "scope_key"])
    op.create_table(
        "data_subject_requests",
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column("workspace_id", UUID, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_user_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("request_kind", sa.String(30), nullable=False),
        sa.Column("identifier_kind", sa.String(20), nullable=False),
        sa.Column("subject_fingerprint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="received"),
        sa.Column("deleted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=UTC_NOW),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("request_kind IN ('access','rectification','erasure','opposition')", name="ck_data_subject_request_kind"),
        sa.CheckConstraint("status IN ('received','completed','rejected')", name="ck_data_subject_request_status"),
    )
    op.create_index("ix_dsr_workspace_requested", "data_subject_requests", ["workspace_id", "requested_at"])
    op.create_table(
        "contacts",
        _id(),
        sa.Column("workspace_id", UUID, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lead_id", UUID, sa.ForeignKey("leads.id", ondelete="CASCADE")),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("normalized_value", sa.String(500), nullable=False),
        sa.Column("display_value", sa.String(500), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("source_type", sa.String(30), nullable=False, server_default="official_website"),
        sa.Column("source_url", sa.String(2048)),
        sa.Column("source_request_id", UUID, sa.ForeignKey("data_subject_requests.id", ondelete="SET NULL")),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("extraction_method", sa.String(30), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("classification", sa.String(40), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evidence_sha256", sa.String(64), nullable=False),
        sa.Column("rules_version", sa.String(80), nullable=False),
        sa.CheckConstraint("kind IN ('email','phone')", name="ck_contact_kind"),
        sa.CheckConstraint("source_type IN ('official_website','data_subject_request')", name="ck_contact_source_type"),
        sa.CheckConstraint("classification IN ('generic_business','named_professional')", name="ck_contact_classification"),
        sa.CheckConstraint("extraction_method IN ('regex','mailto','structured_data')", name="ck_contact_extraction_method"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_contact_confidence"),
    )
    op.create_index("ix_contacts_workspace_expiry", "contacts", ["workspace_id", "expires_at"])
    op.create_index("ix_contacts_workspace_fingerprint", "contacts", ["workspace_id", "kind", "fingerprint"])

    if op.get_bind().dialect.name == "postgresql":
        predicate = "workspace_id = NULLIF(current_setting('app.workspace_id', true), '')::uuid"
        for table in ("workspace_privacy_policies", "contacts", "data_subject_requests"):
            op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
            op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
            op.execute(
                f'CREATE POLICY "{table}_workspace_isolation" ON "{table}" '
                f"USING ({predicate}) WITH CHECK ({predicate})"
            )
        op.execute('ALTER TABLE "suppression_entries" ENABLE ROW LEVEL SECURITY')
        op.execute('ALTER TABLE "suppression_entries" FORCE ROW LEVEL SECURITY')
        op.execute(
            'CREATE POLICY "suppression_entries_read" ON "suppression_entries" FOR SELECT '
            f"USING (workspace_id IS NULL OR {predicate})"
        )
        op.execute(
            'CREATE POLICY "suppression_entries_insert" ON "suppression_entries" FOR INSERT '
            f"WITH CHECK (workspace_id IS NULL OR {predicate})"
        )
        op.execute(
            'CREATE POLICY "suppression_entries_workspace_update" ON "suppression_entries" FOR UPDATE '
            f"USING ({predicate}) WITH CHECK ({predicate})"
        )
        op.execute(
            'CREATE POLICY "suppression_entries_workspace_delete" ON "suppression_entries" FOR DELETE '
            f"USING ({predicate})"
        )
        op.execute(
            "DO $$ BEGIN "
            "IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'leadhunter_app') THEN "
            "GRANT SELECT, INSERT, UPDATE, DELETE ON workspace_privacy_policies, contacts, suppression_entries, data_subject_requests TO leadhunter_app; "
            "END IF; "
            "IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'leadhunter_worker') THEN "
            "GRANT SELECT, INSERT, UPDATE, DELETE ON workspace_privacy_policies, contacts, suppression_entries, data_subject_requests TO leadhunter_worker; "
            "END IF; END $$"
        )
        op.execute(
            "CREATE OR REPLACE FUNCTION public.app_active_workspace_ids() "
            "RETURNS TABLE(workspace_id uuid) LANGUAGE sql SECURITY DEFINER "
            "SET search_path = pg_catalog, public AS $$ "
            "SELECT id FROM public.workspaces WHERE is_active IS TRUE ORDER BY id $$"
        )
        op.execute(
            "REVOKE ALL ON FUNCTION public.app_active_workspace_ids() FROM PUBLIC"
        )
        op.execute(
            "DO $$ BEGIN "
            "IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'leadhunter_worker') THEN "
            "REVOKE SELECT ON workspaces FROM leadhunter_worker; "
            "GRANT EXECUTE ON FUNCTION public.app_active_workspace_ids() TO leadhunter_worker; "
            "END IF; END $$"
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP FUNCTION IF EXISTS public.app_active_workspace_ids()")
        op.execute(
            "DO $$ BEGIN "
            "IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'leadhunter_worker') THEN "
            "GRANT SELECT ON workspaces TO leadhunter_worker; "
            "END IF; END $$"
        )
    op.drop_index("ix_contacts_workspace_fingerprint", table_name="contacts")
    op.drop_index("ix_contacts_workspace_expiry", table_name="contacts")
    op.drop_table("contacts")
    op.drop_index("ix_dsr_workspace_requested", table_name="data_subject_requests")
    op.drop_table("data_subject_requests")
    op.drop_index("ix_suppression_lookup", table_name="suppression_entries")
    op.drop_table("suppression_entries")
    op.drop_table("workspace_privacy_policies")
