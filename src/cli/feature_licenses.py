"""Local license administration without provider credentials or network calls."""
import argparse
import json
from dataclasses import asdict
from pathlib import Path
from uuid import UUID

from src.application.container import ApplicationContainer
from src.domain.feature_licenses import LicenseError
from src.licensing.verification import TOKEN_LIMIT
from src.settings import ApplicationSettings, SettingsError


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Licenze locali delle funzioni Lead Hunter")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("installation-id")
    commands.add_parser("status")
    commands.add_parser("import").add_argument("file", type=Path)
    commands.add_parser("revoke").add_argument("license_id", type=UUID)
    args = parser.parse_args(argv)
    try:
        scope, licenses, _ = ApplicationContainer(ApplicationSettings()).build_local_license_service()
        if args.command == "installation-id":
            print(scope.installation_id)
        else:
            if args.command == "import":
                with args.file.open("rb") as handle:
                    raw = handle.read(TOKEN_LIMIT + 1)
                if len(raw) > TOKEN_LIMIT:
                    raise LicenseError("license_invalid")
                summary = licenses.import_license(scope, raw.decode("ascii").strip())
            elif args.command == "revoke":
                summary = licenses.revoke_license(scope, args.license_id)
            else:
                summary = licenses.summary(scope)
            print(json.dumps(asdict(summary), default=str, ensure_ascii=False))
        return 0
    except (LicenseError, SettingsError, OSError, UnicodeError) as error:
        print(error.code if isinstance(error, LicenseError) else "license_storage_unavailable")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
