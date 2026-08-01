import unittest

from src.application.audit_log import append_audit_event
from src.infrastructure.models import AuditEventModel
from tests.platform_helpers import platform_fixture


class AuditLogTests(unittest.TestCase):
    def test_details_are_allowlisted_and_bounded(self):
        database, _, _, _ = platform_fixture()
        with database.session() as session:
            append_audit_event(
                session,
                action="x" * 200,
                details={"provider": "p" * 600, "password": "must-not-exist"},
            )
        with database.session() as session:
            event = session.query(AuditEventModel).one()
            self.assertEqual(len(event.action), 120)
            self.assertEqual(len(event.details["provider"]), 500)
            self.assertNotIn("password", event.details)
        database.engine.dispose()


if __name__ == "__main__":
    unittest.main()
