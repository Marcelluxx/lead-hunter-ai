"""Runtime-only, licensed diagnostic capture; separate from customer report data."""
from __future__ import annotations

import json
import os
import re
import tempfile
import time
import uuid
from io import BytesIO
from pathlib import Path
from threading import RLock
from zipfile import ZipFile, ZIP_DEFLATED, BadZipFile

from src.domain.discovery import ensure_provider_payload_absent, ProviderPayloadError
from src.domain.feature_licenses import FeatureAction
from src.security.privacy import redact_sensitive_text

MAX_RECORD_BYTES = 1024 * 1024
MAX_TOTAL_BYTES = 8 * MAX_RECORD_BYTES
MAX_RECORDS = 256
KINDS = frozenset({'page', 'css', 'processed_page', 'evidence', 'llm_request',
                   'llm_response', 'summary', 'error'})
SECRET_KEY = re.compile(r'(?i)(password|secret|token|authorization|cookie|api.?key|private.?key)')


class DiagnosticError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def purge_diagnostic_archives(root: Path, *, now=None) -> int:
    """Remove expired owned archives only from the dedicated, non-symlink root."""
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        return 0
    now = int(time.time()) if now is None else now
    if type(now) is not int:
        raise DiagnosticError('diagnostic_invalid')
    resolved = root.resolve()
    removed = 0
    for path in root.iterdir():
        if path.is_symlink() or not path.is_file() or path.suffix != '.zip':
            continue
        try:
            if str(uuid.UUID(path.stem)) != path.stem or path.resolve().parent != resolved:
                continue
            if path.stat().st_size > 16 * MAX_RECORD_BYTES:
                continue
            with ZipFile(path) as archive:
                if archive.getinfo('manifest.json').file_size > 4096:
                    continue
                manifest = json.loads(archive.read('manifest.json'))
            if (type(manifest) is dict and manifest.get('schema_version') == 1
                    and manifest.get('classification') == 'PRIVATE_REDACTED_DIAGNOSTICS'
                    and manifest.get('run_id') == path.stem
                    and type(manifest.get('expires_at')) is int
                    and manifest['expires_at'] <= now):
                path.unlink()
                removed += 1
        except (OSError, ValueError, KeyError, BadZipFile, RuntimeError):
            continue
    return removed


class DiagnosticSession:
    def __init__(self, access, context_factory, *, retention_hours=24, secrets=()):
        if type(retention_hours) is not int or not 1 <= retention_hours <= 168:
            raise DiagnosticError('diagnostic_invalid')
        if not all(type(value) is str for value in secrets):
            raise DiagnosticError('diagnostic_invalid')
        self._access, self._context_factory = access, context_factory
        self._secrets = tuple(value for value in secrets if value)
        self._records, self._total = [], 0
        self._lock, self._sealed = RLock(), False
        self.run_id = uuid.uuid4()
        claims = self.require_execute()
        self._created_at = access.licenses.clock.now_epoch()
        self._expires_at = min(claims.expires_at, self._created_at + retention_hours * 3600)

    def require_execute(self):
        claims = self._access.require(self._context_factory(), 'diagnostics.full', action=FeatureAction.EXECUTE)
        if hasattr(self, '_expires_at') and self._access.licenses.clock.now_epoch() >= self._expires_at:
            raise DiagnosticError('diagnostic_expired')
        return claims

    def require_view(self):
        claims = self._access.require(self._context_factory(), 'diagnostics.full', action=FeatureAction.VIEW)
        if self._access.licenses.clock.now_epoch() >= self._expires_at:
            raise DiagnosticError('diagnostic_expired')
        return claims

    def _redact(self, value, depth=0):
        if depth > 10:
            raise DiagnosticError('diagnostic_invalid')
        if isinstance(value, dict):
            if len(value) > 256 or not all(type(key) is str and len(key) <= 256 for key in value):
                raise DiagnosticError('diagnostic_invalid')
            return {key: '[REDACTED_SECRET]' if SECRET_KEY.search(key) else self._redact(item, depth + 1)
                    for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            if len(value) > 256:
                raise DiagnosticError('diagnostic_invalid')
            return [self._redact(item, depth + 1) for item in value]
        if type(value) is str:
            if len(value) > MAX_RECORD_BYTES:
                raise DiagnosticError('diagnostic_limit_exceeded')
            for secret in self._secrets:
                value = value.replace(secret, '[REDACTED_SECRET]')
            # Quoted JSON keys and JWTs need coverage beyond the shared log redactor.
            value = re.sub(r'(?i)([\"\x27](?:password|secret|token|api[_-]?key)[\"\x27]\s*:\s*[\"\x27])[^\"\x27]*',
                           r'\1[REDACTED_SECRET]', value)
            value = re.sub(r'\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b', '[REDACTED_TOKEN]', value)
            return redact_sensitive_text(value, max_length=MAX_RECORD_BYTES + 1)
        if value is None or type(value) in (int, float, bool):
            return value
        raise DiagnosticError('diagnostic_invalid')

    def capture(self, kind: str, payload: dict) -> None:
        self.require_execute()
        if kind not in KINDS or type(payload) is not dict:
            raise DiagnosticError('diagnostic_invalid')
        try:
            ensure_provider_payload_absent(payload)
            encoded = json.dumps({'kind': kind, 'payload': self._redact(payload)},
                                 ensure_ascii=False, allow_nan=False).encode('utf-8')
        except (ProviderPayloadError, TypeError, OverflowError, UnicodeError) as exc:
            raise DiagnosticError('diagnostic_invalid') from None
        except ValueError as exc:
            if isinstance(exc, DiagnosticError):
                raise
            raise DiagnosticError('diagnostic_invalid') from None
        with self._lock:
            self.require_execute()
            if self._sealed:
                raise DiagnosticError('diagnostic_closed')
            if len(encoded) > MAX_RECORD_BYTES or self._total + len(encoded) > MAX_TOTAL_BYTES or len(self._records) >= MAX_RECORDS:
                raise DiagnosticError('diagnostic_limit_exceeded')
            self._records.append(encoded)
            self._total += len(encoded)

    def seal(self):
        self.require_view()
        with self._lock:
            self._sealed = True

    def export_bytes(self) -> bytes:
        self.require_view()
        with self._lock:
            records = tuple(self._records)
        manifest = {'schema_version': 1, 'run_id': str(self.run_id), 'created_at': self._created_at,
                    'expires_at': self._expires_at, 'record_count': len(records),
                    'classification': 'PRIVATE_REDACTED_DIAGNOSTICS'}
        output = BytesIO()
        with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
            archive.writestr('manifest.json', json.dumps(manifest))
            for index, record in enumerate(records, 1):
                archive.writestr(f'event-{index:06d}.json', record)
        self.require_view()
        return output.getvalue()

    def save(self, destination: Path) -> Path:
        data = self.export_bytes()
        path, temporary = Path(destination), None
        try:
            self.require_view()
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode='wb', prefix='.diagnostic-', dir=path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            self.require_view()
            os.replace(temporary, path)
            temporary = None
            return path
        except OSError:
            raise DiagnosticError('diagnostic_write_failed') from None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def __reduce_ex__(self, protocol):
        raise TypeError('runtime_diagnostics_not_serializable')

    def __repr__(self):
        return '<DiagnosticSession>'
