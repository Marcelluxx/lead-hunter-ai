"""Optional controls; availability never replaces engine authorization."""
from collections.abc import Callable
import streamlit as st

from src.application.rating_filters import RatingFilterGuard
from src.domain.feature_licenses import LicenseError
from src.domain.rating_filters import RatingFilterCriteria
from src.settings import SettingsError


def render_rating_filter_controls(*, guard_factory: Callable[[], RatingFilterGuard]) -> RatingFilterCriteria | None:
    available = True
    try:
        guard_factory().require_execute()
    except (LicenseError, SettingsError):
        available = False
    selected = st.toggle('Filtra per rating e recensioni', value=False,
                         key='rating_filters_enabled', disabled=not available)
    if not selected:
        return None
    if not available:
        st.caption('Il filtro richiede una licenza valida. Una ricerca filtrata non verrà eseguita come ricerca base.')
        def use_base():
            st.session_state['rating_filters_enabled'] = False
        st.button('Usa la ricerca base', key='rating_filter_use_base', on_click=use_base)
    rating = st.number_input('Soglia rating (superiore a)', min_value=0.0, max_value=5.0,
                             value=3.9, step=0.1, key='rating_filter_min_rating', disabled=not available)
    count = st.number_input('Numero massimo di recensioni', min_value=1, max_value=2147483647,
                            value=100, step=1, key='rating_filter_max_reviews', disabled=not available)
    st.caption('Include soltanto rating superiori alla soglia e da 1 al massimo di recensioni scelto. '
               'I risultati senza questi dati sono esclusi; le metriche Google non sono conservate o esportate.')
    return RatingFilterCriteria(rating, count)
