import argparse
import getpass
import json
from dataclasses import asdict
from pathlib import Path
from uuid import UUID, uuid4

from src.application.feature_licenses import LicenseService
from src.application.license_clock import SystemClock
from src.domain.feature_licenses import AUDIENCE, LicenseClaims, LicenseError, LicenseScope, StoredGrant, SubjectKind
from src.licensing.catalog import FeatureCatalog
from src.licensing.trust import TrustedLicenseKeys
from src.licensing.verification import LicenseVerifier, TOKEN_LIMIT
from tools.license_issuer.keys import generate_issuer_keys
from tools.license_issuer.issuance import issue_license, parse_license_date


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Emissione privata di licenze Lead Hunter")
    commands = parser.add_subparsers(dest="command", required=True)
    keygen = commands.add_parser("keygen")
    keygen.add_argument("--private-out", type=Path, required=True)
    keygen.add_argument("--public-out", type=Path, required=True)
    issue, inspect = commands.add_parser("issue"), commands.add_parser("inspect")
    for command in (issue, inspect):
        command.add_argument("--kid", required=True)
        command.add_argument("--issuer", default="lead-hunter-owner")
        command.add_argument("--installation-id", type=UUID, required=True)
        command.add_argument("--subject-kind", choices=[kind.value for kind in SubjectKind], required=True)
        command.add_argument("--subject-id", type=UUID, required=True)
        command.add_argument("--workspace-id", type=UUID)
    issue.add_argument("--private-key", type=Path, required=True)
    issue.add_argument("--feature", action="append", required=True)
    issue.add_argument("--not-before", required=True)
    issue.add_argument("--expires-at", required=True)
    issue.add_argument("--out", type=Path, required=True)
    inspect.add_argument("--license-file", type=Path, required=True)
    inspect.add_argument("--public-key", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "keygen":
            password = getpass.getpass("Passphrase della chiave privata: ").encode()
            if getpass.getpass("Ripeti passphrase: ").encode() != password:
                raise LicenseError("license_invalid")
            generate_issuer_keys(private_path=args.private_out, public_path=args.public_out, passphrase=password)
        else:
            scope = LicenseScope(args.installation_id, SubjectKind(args.subject_kind),
                                 args.subject_id, args.workspace_id)
            if args.command == "issue":
                claims = LicenseClaims(1, args.issuer, AUDIENCE, uuid4(), SystemClock().now_epoch(),
                    parse_license_date(args.not_before), parse_license_date(args.expires_at), scope, tuple(args.feature))
                issue_license(claims, private_path=args.private_key,
                    passphrase=getpass.getpass("Passphrase della chiave privata: ").encode(),
                    kid=args.kid, output_path=args.out)
            else:
                with args.license_file.open("rb") as handle:
                    token = handle.read(TOKEN_LIMIT + 1).decode("ascii").strip()
                verifier = LicenseVerifier(TrustedLicenseKeys(args.issuer,
                    {args.kid: args.public_key.read_bytes()}), FeatureCatalog())
                claims = verifier.decode_verified(token, scope=scope)
                class InspectRepository:
                    def read(self, requested_scope):
                        return StoredGrant(token, claims.license_id, False)
                summary = LicenseService(InspectRepository(), verifier, SystemClock()).summary(scope)
                print(json.dumps(asdict(summary), default=str, ensure_ascii=False))
        return 0
    except (LicenseError, OSError, ValueError, UnicodeError) as error:
        print(error.code if isinstance(error, LicenseError) else "license_invalid")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
