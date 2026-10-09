"""Reference export delivered inline after current authorization."""
from __future__ import annotations

import base64
from collections.abc import Callable

import streamlit as st
import streamlit.components.v1 as components

from src.application.reference_exports import ReferenceExportService
from src.domain.feature_licenses import FeatureAction, LicenseError
from src.domain.place_references import GooglePlaceReference, ReferenceExportError
from src.settings import SettingsError


def _reference_download_html(data: bytes) -> str:
    encoded = base64.b64encode(data).decode('ascii')
    return ('<!doctype html><html lang="it"><body>'
            '<a download="riferimenti_google_maps.xlsx" '
            'href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,'
            + encoded + '">Scarica Excel dei riferimenti</a></body></html>')


def render_reference_export_panel(*, place_ids: tuple[str, ...],
                                   service_factory: Callable[[], ReferenceExportService]) -> None:
    if not place_ids:
        return
    st.markdown('### Export riferimenti senza sito')
    st.caption('Il file contiene soltanto Place ID e link Google Maps dell’ultima ricerca. '
               'La preparazione e la consegna richiedono una licenza valida.')
    if st.button('Prepara Excel dei riferimenti', key='reference_export_prepare'):
        try:
            service = service_factory()
            data = service.export_bytes(GooglePlaceReference(value) for value in place_ids)
            html = _reference_download_html(data)
            # srcdoc carries bytes at this authorized delivery. No static media URL
            # is registered and no payload is retained in session_state for reruns.
            service.require_access(action=FeatureAction.VIEW)
            components.html(html, height=55)
        except (LicenseError, ReferenceExportError) as exc:
            st.error(f'Export riferimenti non disponibile: {exc.code}')
        except SettingsError:
            st.error('Configurazione delle licenze non disponibile. Verifica le impostazioni locali.')
