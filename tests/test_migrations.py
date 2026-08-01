import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


class MigrationTests(unittest.TestCase):
    def test_initial_migration_upgrades_and_downgrades_clean_database(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory, "platform.sqlite")
            database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"
            config = Config("alembic.ini")
            config.set_main_option("sqlalchemy.url", database_url)

            with patch.dict(
                os.environ,
                {"DATABASE_URL": "", "DATABASE_MIGRATION_URL": ""},
            ):
                command.upgrade(config, "head")
                engine = create_engine(database_url)
                try:
                    tables = set(inspect(engine).get_table_names())
                    self.assertIn("users", tables)
                    self.assertIn("workspaces", tables)
                    self.assertIn("usage_ledger", tables)
                    self.assertIn("lead_attributes", tables)
                    self.assertIn("provider_references", tables)
                    self.assertIn("contacts", tables)
                    self.assertIn("suppression_entries", tables)
                    self.assertIn("data_subject_requests", tables)
                finally:
                    engine.dispose()

                command.downgrade(config, "base")
                engine = create_engine(database_url)
                try:
                    self.assertEqual(
                        inspect(engine).get_table_names(), ["alembic_version"]
                    )
                finally:
                    engine.dispose()


if __name__ == "__main__":
    unittest.main()
