"""Administrative public trust configuration, separate from login keys."""
import os
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from src.domain.feature_licenses import LicenseError
from src.licensing.trust import TrustedLicenseKeys
from src.licensing.verification import strict_json
from src.settings import SettingsError


@dataclass(frozen=True)
class LicenseSettings:
    issuer: str
    trust_file: Path | None
    local_state_dir: Path
    installation_id: UUID | None

    @classmethod
    def from_environment(cls):
        try:
            identity = os.getenv("LEADHUNTER_INSTALLATION_ID", "")
            trust = os.getenv("LEADHUNTER_LICENSE_TRUST_FILE", "")
            return cls(os.getenv("LEADHUNTER_LICENSE_ISSUER", "lead-hunter-owner"),
                       Path(trust).resolve() if trust else None,
                       Path(os.getenv("LEADHUNTER_LICENSE_STATE_DIR") or ".leadhunter-state").resolve(),
                       UUID(identity) if identity else None)
        except (ValueError, OSError):
            raise SettingsError("Configurazione licenze non valida.") from None

    def load_trusted_keys(self):
        try:
            if self.trust_file is None:
                return TrustedLicenseKeys(self.issuer, {})
            with self.trust_file.open("rb") as handle:
                raw = handle.read(65537)
            if len(raw) > 65536:
                raise ValueError()
            data = strict_json(raw)
            if (type(data) is not dict or set(data) != {"version", "issuer", "keys"} or
                    type(data["version"]) is not int or data["version"] != 1 or
                    data["issuer"] != self.issuer or type(data["keys"]) is not dict or not data["keys"]):
                raise ValueError()
            return TrustedLicenseKeys(self.issuer, {kid: pem.encode("ascii") for kid, pem in data["keys"].items()})
        except (ValueError, TypeError, OSError, AttributeError, LicenseError):
            raise SettingsError("Configurazione pubblica delle licenze non valida.") from None

    def validate_server(self):
        if self.trust_file is not None and not isinstance(self.installation_id, UUID):
            raise SettingsError("Il licensing server richiede LEADHUNTER_INSTALLATION_ID stabile.")
        self.load_trusted_keys()
