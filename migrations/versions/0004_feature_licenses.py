"""Scoped expiring feature grants and deployment time high-watermark."""
from alembic import op
import sqlalchemy as sa

revision = "0004_feature_licenses"
down_revision = "0003_contact_privacy_governance"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "feature_license_grants",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("license_id", sa.Uuid(), nullable=False, unique=True),
        sa.Column("installation_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("issued_at", sa.BigInteger(), nullable=False),
        sa.Column("not_before", sa.BigInteger(), nullable=False),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),
        sa.Column("features", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("imported_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("NOT active OR revoked_at IS NULL", name="ck_license_active_not_revoked"),
        sa.CheckConstraint("issued_at >= 0 AND issued_at <= not_before AND not_before < expires_at AND expires_at <= 253402300799", name="ck_license_dates"),
    )
    op.create_index("uq_feature_license_active_subject", "feature_license_grants",
                    ["workspace_id", "user_id"], unique=True, postgresql_where=sa.text("active"),
                    sqlite_where=sa.text("active = 1"))
    op.create_table(
        "license_clock_state",
        sa.Column("installation_id", sa.Uuid(), primary_key=True),
        sa.Column("maximum_epoch", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("maximum_epoch BETWEEN 0 AND 253402300799", name="ck_license_clock_epoch"))
    if op.get_bind().dialect.name != "postgresql":
        return
    predicate = "workspace_id = NULLIF(current_setting('app.workspace_id', true), '')::uuid"
    op.execute("ALTER TABLE feature_license_grants ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE feature_license_grants FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY feature_license_workspace_isolation ON feature_license_grants "
               f"USING ({predicate}) WITH CHECK ({predicate})")
    op.execute("""
        CREATE FUNCTION public.app_advance_license_clock(p_installation_id uuid, p_observed_epoch bigint)
        RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
        DECLARE result bigint;
        BEGIN
          IF NULLIF(current_setting('app.installation_id', true), '')::uuid IS DISTINCT FROM p_installation_id
             OR p_observed_epoch IS NULL OR p_observed_epoch < 0 OR p_observed_epoch > 253402300799 THEN
            RAISE EXCEPTION 'invalid license clock context' USING ERRCODE = '42501';
          END IF;
          INSERT INTO public.license_clock_state(installation_id, maximum_epoch)
          VALUES(p_installation_id, p_observed_epoch)
          ON CONFLICT(installation_id) DO UPDATE
          SET maximum_epoch = GREATEST(public.license_clock_state.maximum_epoch, EXCLUDED.maximum_epoch)
          RETURNING maximum_epoch INTO result;
          RETURN result;
        END $$;
    """)
    op.execute("REVOKE ALL ON FUNCTION public.app_advance_license_clock(uuid, bigint) FROM PUBLIC")
    op.execute("""
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'leadhunter_app') THEN
            GRANT SELECT, INSERT, UPDATE ON feature_license_grants TO leadhunter_app;
            REVOKE DELETE ON feature_license_grants FROM leadhunter_app;
            REVOKE ALL ON license_clock_state FROM leadhunter_app;
            GRANT EXECUTE ON FUNCTION public.app_advance_license_clock(uuid, bigint) TO leadhunter_app;
          END IF;
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'leadhunter_worker') THEN
            REVOKE ALL ON feature_license_grants, license_clock_state FROM leadhunter_worker;
            GRANT SELECT ON feature_license_grants TO leadhunter_worker;
            GRANT EXECUTE ON FUNCTION public.app_advance_license_clock(uuid, bigint) TO leadhunter_worker;
          END IF;
        END $$;
    """)


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP FUNCTION public.app_advance_license_clock(uuid, bigint)")
    op.drop_table("license_clock_state")
    op.drop_table("feature_license_grants")
