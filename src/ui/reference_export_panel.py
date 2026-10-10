"""Reference export delivered inline after current authorization."""
from __future__ import annotations

from collections.abc import Callable

import streamlit as st

from src.application.reference_exports import ReferenceExportService
from src.application.rating_filters import RatingFilterGuard
from src.ui.inline_download import render_inline_xlsx_download
from src.domain.feature_licenses import FeatureAction, LicenseError
from src.domain.place_references import GooglePlaceReference, ReferenceExportError
from src.settings import SettingsError


def render_reference_export_panel(*, place_ids: tuple[str, ...],
                                   service_factory: Callable[[], ReferenceExportService],
                                   origin: RatingFilterGuard | None = None) -> None:
    if not place_ids:
        return
    if origin is not None:
        try:
            origin.require_view()
        except LicenseError as exc:
            st.error(f'Risultati filtrati non disponibili: {exc.code}')
            return
    st.markdown('### Export riferimenti senza sito')
    st.caption('Il file contiene soltanto Place ID e link Google Maps dell’ultima ricerca. '
               'La preparazione e la consegna richiedono una licenza valida.')
    if st.button('Prepara Excel dei riferimenti', key='reference_export_prepare'):
        try:
            service = service_factory()
            data = service.export_bytes((GooglePlaceReference(value) for value in place_ids), origin=origin)
            # srcdoc carries bytes at this authorized delivery. No static media URL
            # is registered and no payload is retained in session_state for reruns.
            def require_delivery():
                service.require_access(action=FeatureAction.VIEW)
                if origin is not None:
                    origin.require_view()
            render_inline_xlsx_download(data, filename='riferimenti_google_maps.xlsx',
                                       label='Scarica Excel dei riferimenti', before_delivery=require_delivery)
        except (LicenseError, ReferenceExportError) as exc:
            st.error(f'Export riferimenti non disponibile: {exc.code}')
        except SettingsError:
            st.error('Configurazione delle licenze non disponibile. Verifica le impostazioni locali.')
