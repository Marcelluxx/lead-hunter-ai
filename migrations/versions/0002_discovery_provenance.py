"""Add compliant discovery provenance and retention tables."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_discovery_provenance"
down_revision = "0001_platform_identity_workspace"
branch_labels = None
depends_on = None

UUID = sa.Uuid()
UTC_NOW = sa.text("CURRENT_TIMESTAMP")


def _id() -> sa.Column:
    return sa.Column("id", UUID, primary_key=True, nullable=False)


def upgrade() -> None:
    op.create_table(
        "leads",
        _id(),
        sa.Column("workspace_id", UUID, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", UUID, sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="verified"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=UTC_NOW),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=UTC_NOW),
    )
    op.create_index("ix_leads_workspace_job", "leads", ["workspace_id", "job_id"])
    op.create_table(
        "lead_evidence",
        _id(),
        sa.Column("workspace_id", UUID, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lead_id", UUID, sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_url", sa.String(2048), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_lead_evidence_workspace_lead", "lead_evidence", ["workspace_id", "lead_id"])
    op.create_table(
        "lead_attributes",
        _id(),
        sa.Column("workspace_id", UUID, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lead_id", UUID, sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("evidence_id", UUID, sa.ForeignKey("lead_evidence.id", ondelete="SET NULL")),
        sa.Column("field_name", sa.String(100), nullable=False),
        sa.Column("value_text", sa.Text(), nullable=False),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("source_url", sa.String(2048)),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1"),
        sa.Column("data_classification", sa.String(80), nullable=False, server_default="business_contact"),
        sa.CheckConstraint("source IN ('official_website','user_input')", name="ck_lead_attribute_source"),
        sa.UniqueConstraint("lead_id", "field_name"),
    )
    op.create_index("ix_lead_attributes_workspace_expiry", "lead_attributes", ["workspace_id", "expires_at"])
    op.create_table(
        "provider_references",
        _id(),
        sa.Column("workspace_id", UUID, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", UUID, sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lead_id", UUID, sa.ForeignKey("leads.id", ondelete="CASCADE")),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("external_id", sa.String(500), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("refresh_after", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "provider", "external_id"),
    )
    op.create_index("ix_provider_references_refresh", "provider_references", ["workspace_id", "refresh_after"])
    op.create_table(
        "retention_events",
        _id(),
        sa.Column("workspace_id", UUID, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("deleted_count", sa.Integer(), nullable=False),
        sa.Column("ran_at", sa.DateTime(timezone=True), nullable=False, server_default=UTC_NOW),
    )
    op.create_index("ix_retention_events_workspace_run", "retention_events", ["workspace_id", "ran_at"])

    if op.get_bind().dialect.name == "postgresql":
        predicate = "workspace_id = NULLIF(current_setting('app.workspace_id', true), '')::uuid"
        for table in ("leads", "lead_evidence", "lead_attributes", "provider_references", "retention_events"):
            op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
            op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
            op.execute(
                f'CREATE POLICY "{table}_workspace_isolation" ON "{table}" '
                f"USING ({predicate}) WITH CHECK ({predicate})"
            )
        op.execute(
            "DO $$ BEGIN "
            "IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'leadhunter_app') THEN "
            "GRANT SELECT, INSERT, UPDATE, DELETE ON leads, lead_evidence, lead_attributes, provider_references, retention_events TO leadhunter_app; "
            "END IF; "
            "IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'leadhunter_worker') THEN "
            "GRANT SELECT, INSERT, UPDATE, DELETE ON leads, lead_evidence, lead_attributes, provider_references, retention_events TO leadhunter_worker; "
            "END IF; END $$"
        )


def downgrade() -> None:
    op.drop_index("ix_retention_events_workspace_run", table_name="retention_events")
    op.drop_table("retention_events")
    op.drop_index("ix_provider_references_refresh", table_name="provider_references")
    op.drop_table("provider_references")
    op.drop_index("ix_lead_attributes_workspace_expiry", table_name="lead_attributes")
    op.drop_table("lead_attributes")
    op.drop_index("ix_lead_evidence_workspace_lead", table_name="lead_evidence")
    op.drop_table("lead_evidence")
    op.drop_index("ix_leads_workspace_job", table_name="leads")
    op.drop_table("leads")
