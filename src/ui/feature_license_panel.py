"""The local console displays entitlements without executing planned modules."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import streamlit as st

from src.domain.feature_licenses import FeatureContext, LicenseError
from src.domain.identity import Permission
from src.licensing.verification import TOKEN_LIMIT


def display_expiry(epoch):
    if epoch is None:
        return "Nessuna scadenza assegnata"
    instant = datetime.fromtimestamp(epoch, timezone.utc)
    try:
        return instant.astimezone(ZoneInfo("Europe/Rome")).strftime("%d/%m/%Y %H:%M:%S %Z") + " (Europe/Rome)"
    except OverflowError:
        return instant.isoformat() + " (UTC)"


def render_feature_license_panel(*, scope, licenses, access) -> None:
    st.markdown("### Funzioni riservate")
    st.caption("Identificativo da comunicare per ottenere una licenza:")
    st.code(str(scope.installation_id), language=None)
    upload = st.file_uploader("File di licenza", type=["lh", "txt", "jwt"], key="license_upload")
    if st.button("Importa licenza", key="license_import", disabled=upload is None):
        try:
            upload.seek(0)
            raw = upload.read(TOKEN_LIMIT + 1)
            if len(raw) > TOKEN_LIMIT:
                raise LicenseError("license_invalid")
            licenses.import_license(scope, raw.decode("ascii").strip())
            st.success("Licenza importata.")
        except (LicenseError, UnicodeError) as error:
            st.error(error.code if isinstance(error, LicenseError) else "license_invalid")
    summary = licenses.summary(scope)
    st.caption(f"Stato licenza: {summary.license_status}")
    if summary.expires_at is not None:
        st.caption(f"Scadenza: {display_expiry(summary.expires_at)}")
    if summary.license_id is not None and st.button("Revoca licenza locale", key="license_revoke"):
        try:
            licenses.revoke_license(scope, summary.license_id)
            st.success("Licenza revocata.")
        except LicenseError as error:
            st.error(error.code)
    context = FeatureContext(scope, frozenset(Permission), False, True)
    for feature in access.list_status(context):
        st.markdown(f"**{feature.label}**")
        if feature.module_status == "planned":
            st.info("Autorizzato, modulo non ancora disponibile" if feature.granted else "Modulo non ancora disponibile")
        else:
            st.caption("Autorizzato" if feature.granted else "Accesso non attivo")
