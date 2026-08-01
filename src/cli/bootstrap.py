"""One-time, non-public platform bootstrap.

All values are read from environment variables so passwords do not enter shell
history through command arguments.
"""

from __future__ import annotations

import os

from ..application.workspaces import bootstrap_platform
from ..infrastructure.crypto import PasswordService
from ..infrastructure.database import Database


def main() -> None:
    required = {
        "DATABASE_MIGRATION_URL": os.getenv("DATABASE_MIGRATION_URL", ""),
        "LEADHUNTER_BOOTSTRAP_EMAIL": os.getenv("LEADHUNTER_BOOTSTRAP_EMAIL", ""),
        "LEADHUNTER_BOOTSTRAP_PASSWORD": os.getenv("LEADHUNTER_BOOTSTRAP_PASSWORD", ""),
        "LEADHUNTER_BOOTSTRAP_NAME": os.getenv("LEADHUNTER_BOOTSTRAP_NAME", ""),
        "LEADHUNTER_BOOTSTRAP_WORKSPACE_SLUG": os.getenv(
            "LEADHUNTER_BOOTSTRAP_WORKSPACE_SLUG", ""
        ),
        "LEADHUNTER_BOOTSTRAP_WORKSPACE_NAME": os.getenv(
            "LEADHUNTER_BOOTSTRAP_WORKSPACE_NAME", ""
        ),
        "LEADHUNTER_BOOTSTRAP_HARD_LIMIT": os.getenv(
            "LEADHUNTER_BOOTSTRAP_HARD_LIMIT", ""
        ),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise SystemExit(f"Variabili bootstrap mancanti: {', '.join(missing)}")
    database = Database(required["DATABASE_MIGRATION_URL"])
    try:
        with database.session() as session:
            user, workspace = bootstrap_platform(
                session,
                email=required["LEADHUNTER_BOOTSTRAP_EMAIL"],
                password=required["LEADHUNTER_BOOTSTRAP_PASSWORD"],
                display_name=required["LEADHUNTER_BOOTSTRAP_NAME"],
                workspace_slug=required["LEADHUNTER_BOOTSTRAP_WORKSPACE_SLUG"],
                workspace_name=required["LEADHUNTER_BOOTSTRAP_WORKSPACE_NAME"],
                hard_limit=required["LEADHUNTER_BOOTSTRAP_HARD_LIMIT"],
                passwords=PasswordService(),
            )
        print(f"Bootstrap completato: user={user.id} workspace={workspace.id}")
    finally:
        database.engine.dispose()


if __name__ == "__main__":
    main()
