from __future__ import annotations

import os
import uuid

from sqlalchemy import delete

from src.infrastructure.database import Database
from src.infrastructure.models import UserModel, WorkspaceModel


OWNER_URL = os.getenv("TEST_DATABASE_OWNER_URL", "")
APP_URL = os.getenv("TEST_DATABASE_APP_URL", "")
WORKER_URL = os.getenv("TEST_DATABASE_WORKER_URL", "")
POSTGRES_AVAILABLE = bool(OWNER_URL and APP_URL and WORKER_URL)


def databases() -> tuple[Database, Database, Database]:
    return Database(OWNER_URL), Database(APP_URL), Database(WORKER_URL)


def delete_fixture(owner: Database, workspace_id: uuid.UUID, user_id: uuid.UUID) -> None:
    with owner.session() as session:
        session.execute(delete(WorkspaceModel).where(WorkspaceModel.id == workspace_id))
        session.execute(delete(UserModel).where(UserModel.id == user_id))
