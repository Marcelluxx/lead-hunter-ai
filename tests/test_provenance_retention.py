import unittest
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from src.application.discovery import DiscoveryPersistenceError, DiscoveryPersistenceService
from src.application.retention import RetentionService
from src.domain.discovery import ProviderAttribution, TransientCandidate
from src.domain.provenance import DataSource, FieldProvenance, VerifiedLead
from src.infrastructure.database import Database
from src.infrastructure.models import (
    Base,
    JobModel,
    LeadAttributeModel,
    ProviderReferenceModel,
    RetentionEventModel,
    UserModel,
    WorkspaceModel,
)


class ProvenanceRetentionTests(unittest.TestCase):
    def setUp(self):
        self.database = Database("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.database.engine)
        self.user_id = uuid.uuid4()
        self.workspace_id = uuid.uuid4()
        self.job_id = uuid.uuid4()
        with self.database.session() as session:
            session.add(UserModel(
                id=self.user_id,
                email="provenance@example.test",
                password_hash="hash",
                display_name="Test",
            ))
            session.add(WorkspaceModel(id=self.workspace_id, slug="provenance", name="Provenance"))
            session.flush()
            session.add(JobModel(
                id=self.job_id,
                workspace_id=self.workspace_id,
                created_by=self.user_id,
                kind="discovery",
                idempotency_key="provenance",
                parameters={},
                estimated_cost=Decimal("1"),
            ))

    def tearDown(self):
        self.database.engine.dispose()

    def test_persists_only_place_reference_and_refreshes_after_one_year(self):
        now = datetime.now(timezone.utc)
        candidate = TransientCandidate(
            "google_places", "place-id", "Transient name", None, now,
            ProviderAttribution("google_places", "Google Maps", "terms", "privacy"),
        )
        with self.database.session() as session:
            DiscoveryPersistenceService().persist_provider_reference(
                session,
                workspace_id=self.workspace_id,
                job_id=self.job_id,
                candidate=candidate,
            )
        with self.database.session() as session:
            record = session.scalar(select(ProviderReferenceModel))
            self.assertEqual(record.external_id, "place-id")
            self.assertNotIn("Transient name", str(record.__dict__))
            self.assertEqual((record.refresh_after - record.last_verified_at).days, 365)

    def test_rejects_provider_content_as_persistent_attribute(self):
        provider_provenance = FieldProvenance(
            DataSource.PROVIDER_REFERENCE, None, datetime.now(timezone.utc)
        )
        lead = VerifiedLead(
            "Forbidden", "dentista", "https://example.test",
            provenance={"business_name": provider_provenance},
        )
        with self.assertRaises(DiscoveryPersistenceError):
            with self.database.session() as session:
                DiscoveryPersistenceService().persist_verified_lead(
                    session,
                    workspace_id=self.workspace_id,
                    job_id=self.job_id,
                    lead=lead,
                )

    def test_retention_deletes_only_expired_workspace_attributes_and_audits_count(self):
        now = datetime.now(timezone.utc)
        source = FieldProvenance(
            DataSource.OFFICIAL_WEBSITE,
            "https://example.test",
            now,
            "a" * 64,
            expires_at=now - timedelta(seconds=1),
        )
        lead = VerifiedLead(
            "Expired", "dentista", "https://example.test",
            provenance={"business_name": source, "website": source},
        )
        with self.database.session() as session:
            DiscoveryPersistenceService().persist_verified_lead(
                session,
                workspace_id=self.workspace_id,
                job_id=self.job_id,
                lead=lead,
            )
        with self.database.session() as session:
            deleted = RetentionService().purge_expired_attributes(
                session, workspace_id=self.workspace_id, now=now
            )
            self.assertEqual(deleted, 2)
        with self.database.session() as session:
            self.assertEqual(session.scalars(select(LeadAttributeModel)).all(), [])
            event = session.scalar(select(RetentionEventModel))
            self.assertEqual(event.deleted_count, 2)


if __name__ == "__main__":
    unittest.main()
