"""Atomic local grants, identity, revocation tombstones, and observed time."""
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID, uuid4

from src.domain.feature_licenses import LicenseError, StoredGrant, SubjectKind, valid_epoch
from src.infrastructure.file_lock import file_lock
from src.licensing.verification import strict_json, TOKEN_LIMIT


class LocalLicenseStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    def _write(self, state):
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.root,
                                             prefix=".state-", delete=False) as handle:
                temporary = Path(handle.name)
                json.dump(state, handle, ensure_ascii=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.root / "state.json")
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def _validate(self, state):
        if (type(state) is not dict or set(state) !=
                {"version", "installation_id", "maximum_time", "grant", "revoked_ids"} or
                type(state["version"]) is not int or state["version"] != 1 or
                not valid_epoch(state["maximum_time"]) or type(state["revoked_ids"]) is not list):
            raise ValueError()
        UUID(state["installation_id"])
        revoked = [UUID(value) for value in state["revoked_ids"]]
        if len(revoked) != len(set(revoked)):
            raise ValueError()
        grant = state["grant"]
        if grant is not None:
            if (type(grant) is not dict or set(grant) != {"token", "license_id"} or
                    type(grant["token"]) is not str or len(grant["token"].encode()) > TOKEN_LIMIT):
                raise ValueError()
            UUID(grant["license_id"])

    @contextmanager
    def _state(self):
        try:
            with file_lock(self.root / "state.lock"):
                path = self.root / "state.json"
                if path.exists():
                    state = strict_json(path.read_text(encoding="utf-8"))
                    self._validate(state)
                else:
                    state = dict(version=1, installation_id=str(uuid4()), maximum_time=0,
                                 grant=None, revoked_ids=[])
                    self._write(state)
                yield state
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            raise LicenseError("license_storage_unavailable") from None

    def _check_scope(self, state, scope):
        if (scope.subject_kind is not SubjectKind.INSTALLATION or
                str(scope.installation_id) != state["installation_id"]):
            raise LicenseError("license_subject_mismatch")

    def installation_id(self) -> UUID:
        with self._state() as state:
            return UUID(state["installation_id"])

    def advance(self, observed_epoch: int) -> int:
        if not valid_epoch(observed_epoch):
            raise LicenseError("license_clock_regression")
        with self._state() as state:
            maximum = max(state["maximum_time"], observed_epoch)
            if maximum != state["maximum_time"]:
                state["maximum_time"] = maximum
                self._write(state)
            return maximum

    def read(self, scope):
        with self._state() as state:
            self._check_scope(state, scope)
            grant = state["grant"]
            if grant is None:
                return None
            return StoredGrant(grant["token"], UUID(grant["license_id"]),
                               grant["license_id"] in state["revoked_ids"])

    def _audit(self, event, claims_id, *, actor_id, features=(), expires_at=None):
        data = dict(event=event, license_id=str(claims_id), actor_id=str(actor_id) if actor_id else None,
                    features=list(features), expires_at=expires_at)
        with (self.root / "audit.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(data) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def activate(self, scope, *, token, claims, actor_id=None):
        with self._state() as state:
            self._check_scope(state, scope)
            if claims.scope != scope:
                raise LicenseError("license_subject_mismatch")
            license_id = str(claims.license_id)
            if license_id in state["revoked_ids"]:
                raise LicenseError("license_revoked")
            old = state["grant"]
            if old is not None and old["license_id"] == license_id:
                if old["token"] != token:
                    raise LicenseError("license_invalid")
                return
            if old is not None and old["license_id"] not in state["revoked_ids"]:
                state["revoked_ids"].append(old["license_id"])
            state["grant"] = {"token": token, "license_id": license_id}
            self._write(state)
            self._audit("license.renewed" if old else "license.imported", claims.license_id,
                        actor_id=actor_id, features=claims.features, expires_at=claims.expires_at)

    def revoke(self, scope, *, license_id, actor_id=None):
        with self._state() as state:
            self._check_scope(state, scope)
            grant = state["grant"]
            # Do not create arbitrary tombstones for a license never held here.
            if grant is None or grant["license_id"] != str(license_id):
                return
            if str(license_id) not in state["revoked_ids"]:
                state["revoked_ids"].append(str(license_id))
                self._write(state)
                self._audit("license.revoked", license_id, actor_id=actor_id)
