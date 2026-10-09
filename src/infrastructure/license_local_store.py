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
                {"version", "installation_id", "maximum_time", "grant", "revoked_ids", "audit_events"} or
                type(state["version"]) is not int or state["version"] != 1 or
                not valid_epoch(state["maximum_time"]) or type(state["revoked_ids"]) is not list or
                type(state["audit_events"]) is not list):
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
        for event in state["audit_events"]:
            if (type(event) is not dict or set(event) !=
                    {"event", "license_id", "actor_id", "features", "expires_at"} or
                    event["event"] not in {"license.imported", "license.renewed", "license.revoked"} or
                    type(event["features"]) is not list or
                    any(type(feature) is not str for feature in event["features"]) or
                    (event["expires_at"] is not None and not valid_epoch(event["expires_at"]))):
                raise ValueError()
            UUID(event["license_id"])
            if event["actor_id"] is not None:
                UUID(event["actor_id"])

    def _project_audit(self, state):
        """Best-effort projection; state.json is the atomic audit/grant journal."""
        temporary = None
        try:
            path = self.root / "audit.jsonl"
            data = "".join(json.dumps(event) + "\n" for event in state["audit_events"])
            if path.exists() and path.read_bytes() == data.encode("utf-8"):
                return
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.root,
                                             prefix=".audit-", delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        except OSError:
            # An unavailable projection cannot turn a committed grant into a
            # reported failure. Every later state access retries from the journal.
            pass
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass

    @contextmanager
    def _state(self):
        try:
            with file_lock(self.root / "state.lock"):
                path = self.root / "state.json"
                if path.exists():
                    state = strict_json(path.read_text(encoding="utf-8"))
                    legacy_fields = {"version", "installation_id", "maximum_time", "grant", "revoked_ids"}
                    legacy = type(state) is dict and set(state) == legacy_fields
                    if legacy:
                        audit = self.root / "audit.jsonl"
                        state["audit_events"] = [strict_json(line) for line in
                            audit.read_text(encoding="utf-8").splitlines()] if audit.exists() else []
                    self._validate(state)
                    if legacy:
                        self._write(state)
                else:
                    state = dict(version=1, installation_id=str(uuid4()), maximum_time=0,
                                 grant=None, revoked_ids=[], audit_events=[])
                    self._write(state)
                self._project_audit(state)
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

    def _audit(self, state, event, claims_id, *, actor_id, features=(), expires_at=None):
        data = dict(event=event, license_id=str(claims_id), actor_id=str(actor_id) if actor_id else None,
                    features=list(features), expires_at=expires_at)
        state["audit_events"].append(data)

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
            self._audit(state, "license.renewed" if old else "license.imported", claims.license_id,
                        actor_id=actor_id, features=claims.features, expires_at=claims.expires_at)
            self._write(state)
            self._project_audit(state)

    def revoke(self, scope, *, license_id, actor_id=None):
        with self._state() as state:
            self._check_scope(state, scope)
            grant = state["grant"]
            # Do not create arbitrary tombstones for a license never held here.
            if grant is None or grant["license_id"] != str(license_id):
                return
            if str(license_id) not in state["revoked_ids"]:
                state["revoked_ids"].append(str(license_id))
                self._audit(state, "license.revoked", license_id, actor_id=actor_id)
                self._write(state)
                self._project_audit(state)
