"""Deliver bytes only in the currently authorized inline response."""
import base64
from collections.abc import Callable
from html import escape
import streamlit.components.v1 as components


def _inline_download_html(data: bytes, *, filename: str, label: str, mime_type: str) -> str:
    if mime_type not in ('application/zip', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'):
        raise ValueError('download_mime_invalid')
    encoded = base64.b64encode(data).decode('ascii')
    return ('<!doctype html><html lang="it"><body><a download="' + escape(filename, quote=True)
            + '" href="data:' + mime_type + ';base64,'
            + encoded + '">' + escape(label) + '</a></body></html>')


def _xlsx_download_html(data: bytes, *, filename: str, label: str) -> str:
    return _inline_download_html(data, filename=filename, label=label,
                                 mime_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


def render_inline_download(data: bytes, *, filename: str, label: str, mime_type: str,
                           before_delivery: Callable[[], None]) -> None:
    html = _inline_download_html(data, filename=filename, label=label, mime_type=mime_type)
    before_delivery()
    components.html(html, height=55)


def render_inline_xlsx_download(data: bytes, *, filename: str, label: str,
                                before_delivery: Callable[[], None]) -> None:
    html = _xlsx_download_html(data, filename=filename, label=label)
    before_delivery()
    components.html(html, height=55)
