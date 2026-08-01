import unittest

from src.infrastructure.database import Database
from src.infrastructure.models import Base, WorkspaceModel
from src.workers.retention_scheduler import (
    _schedule_interval,
    enqueue_active_workspaces,
)


class _Publisher:
    def __init__(self):
        self.workspace_ids = []

    def publish(self, workspace_id):
        self.workspace_ids.append(workspace_id)


class RetentionSchedulerTests(unittest.TestCase):
    def setUp(self):
        self.database = Database("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.database.engine)

    def tearDown(self):
        self.database.engine.dispose()

    def test_schedules_only_active_workspaces_and_queue_contains_uuid_only(self):
        with self.database.session() as session:
            session.add_all(
                [
                    WorkspaceModel(slug="active-a", name="A", is_active=True),
                    WorkspaceModel(slug="inactive", name="Inactive", is_active=False),
                    WorkspaceModel(slug="active-b", name="B", is_active=True),
                ]
            )
        publisher = _Publisher()
        with self.database.session() as session:
            count = enqueue_active_workspaces(session, publisher=publisher)
        self.assertEqual(count, 2)
        self.assertEqual(len(publisher.workspace_ids), 2)
        self.assertTrue(all(item.version == 4 for item in publisher.workspace_ids))

    def test_schedule_has_safe_minimum(self):
        self.assertEqual(_schedule_interval(""), 3600)
        with self.assertRaises(ValueError):
            _schedule_interval("60")


if __name__ == "__main__":
    unittest.main()
