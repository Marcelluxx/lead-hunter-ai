import unittest
import uuid

from sqlalchemy import select

from src.application.suppression import SuppressionService
from src.infrastructure.database import Database
from src.infrastructure.models import Base, SuppressionEntryModel


class SuppressionTests(unittest.TestCase):
    def setUp(self):
        self.database = Database("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.database.engine)
        self.service = SuppressionService(b"s" * 32)
        self.workspace_id = uuid.uuid4()

    def tearDown(self):
        self.database.engine.dispose()

    def test_hmac_suppression_is_normalized_scoped_and_idempotent(self):
        with self.database.session() as session:
            first = self.service.suppress(
                session,
                workspace_id=self.workspace_id,
                kind="email",
                value=" Person@Example.IT ",
                scope="workspace",
                reason="opposition",
            )
            second = self.service.suppress(
                session,
                workspace_id=self.workspace_id,
                kind="email",
                value="person@example.it",
                scope="workspace",
                reason="opposition",
            )
            self.assertEqual(first.id, second.id)

        with self.database.session() as session:
            entries = session.scalars(select(SuppressionEntryModel)).all()
            self.assertEqual(len(entries), 1)
            self.assertNotIn("person@example.it", str(entries[0].__dict__).lower())
            self.assertTrue(
                self.service.is_suppressed(
                    session,
                    workspace_id=self.workspace_id,
                    kind="email",
                    value="PERSON@example.it",
                )
            )
            self.assertFalse(
                self.service.is_suppressed(
                    session,
                    workspace_id=uuid.uuid4(),
                    kind="email",
                    value="person@example.it",
                )
            )


if __name__ == "__main__":
    unittest.main()
