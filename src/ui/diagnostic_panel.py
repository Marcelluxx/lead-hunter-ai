"""Reserved single-site diagnostics; no raw payload retained across UI reruns."""
import streamlit as st

from src.application.diagnostics import DiagnosticError
from src.application.diagnostic_runner import run_full_diagnostic
from src.crawler import HybridCrawler
from src.domain.feature_licenses import LicenseError
from src.settings import SettingsError
from .inline_download import render_inline_download


def render_diagnostic_panel(*, container):
    with st.expander('Diagnostica completa riservata'):
        available = True
        try:
            probe = container.build_local_diagnostic_session()
            probe.require_view()
        except (LicenseError, SettingsError, DiagnosticError):
            available = False
        st.caption('Analizza un sito e prepara un archivio privato con pagine, CSS accessibile, '
                   'testi, prompt e risposte AI. Credenziali oscurate; accesso soggetto alla licenza.')
        url = st.text_input('URL del sito da diagnosticare', key='diagnostic_url', disabled=not available)
        pages = st.number_input('Pagine diagnostiche', min_value=1, max_value=20, value=5, key='diagnostic_pages', disabled=not available)
        retention = st.number_input('Conservazione diagnostica (ore)', min_value=1, max_value=168, value=24,
                                    key='diagnostic_retention', disabled=not available)
        if not available:
            st.caption('È necessaria una licenza valida per la diagnostica completa.')
        if st.button('Esegui diagnostica completa', key='diagnostic_run', disabled=not available or not url.strip()):
            try:
                session = container.build_local_diagnostic_session(retention_hours=retention)
                auditor = container.build_auditor(diagnostics=session)
                crawler = HybridCrawler(max_pages=pages, token_mode=container.settings.token_mode, diagnostics=session)
                with st.spinner('Diagnostica in corso…'):
                    run_full_diagnostic(url.strip(), session=session, crawler=crawler, auditor=auditor)
                    data = session.export_bytes()
                render_inline_download(data, filename=f'diagnostica-{session.run_id}.zip',
                    label='Scarica archivio diagnostico privato', mime_type='application/zip', before_delivery=session.require_view)
                st.caption('Conserva il file soltanto per il tempo indicato nel manifest. '
                           'I file già scaricati non vengono ritirati automaticamente.')
            except (LicenseError, DiagnosticError) as exc:
                st.error(f'Diagnostica non disponibile: {exc.code}')
            except SettingsError:
                st.error('Configurazione AI o licenze non disponibile.')
            except Exception:
                st.error('Diagnostica non disponibile: diagnostic_run_failed')
