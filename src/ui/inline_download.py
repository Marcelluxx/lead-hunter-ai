"""Deliver bytes only in the currently authorized inline response."""
import base64
from collections.abc import Callable
from html import escape
import streamlit.components.v1 as components


def _xlsx_download_html(data: bytes, *, filename: str, label: str) -> str:
    encoded = base64.b64encode(data).decode('ascii')
    return ('<!doctype html><html lang="it"><body><a download="' + escape(filename, quote=True)
            + '" href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,'
            + encoded + '">' + escape(label) + '</a></body></html>')


def render_inline_xlsx_download(data: bytes, *, filename: str, label: str,
                                before_delivery: Callable[[], None]) -> None:
    html = _xlsx_download_html(data, filename=filename, label=label)
    before_delivery()
    components.html(html, height=55)
