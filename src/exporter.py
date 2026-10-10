"""
Lead Hunter V3 — Excel Exporter (openpyxl)
Export duale:
  - Modalità "no_website": colonne base (senza ideal_product/sales_hook)
  - Modalità "with_website": colonne estese con audit sito web
"""

import os
import tempfile
from io import BytesIO
from pathlib import Path
from src.application.rating_filters import RatingFilterGuard
from typing import Callable, Union, List, Dict, Any
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

try:
    from .application.export_policy import ExportPolicy
    from .domain.provenance import VerifiedLead
    from .domain.privacy import WorkspacePrivacyPolicy
    from .security.spreadsheet import is_text_cell, sanitize_spreadsheet_value
except (ImportError, ValueError):
    from src.application.export_policy import ExportPolicy
    from src.domain.provenance import VerifiedLead
    from src.domain.privacy import WorkspacePrivacyPolicy
    from src.security.spreadsheet import is_text_cell, sanitize_spreadsheet_value



class DataExporter:
    """Esportatore professionale con formattazione avanzata openpyxl."""

    # Stili header premium
    HEADER_FONT = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    HEADER_FILL = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    HEADER_ALIGNMENT = Alignment(horizontal="center", vertical="center", wrap_text=True)
    HEADER_BORDER = Border(
        bottom=Side(style="medium", color="64748B"),
        right=Side(style="thin", color="334155"),
    )

    # Stili celle dati
    DATA_FONT = Font(name="Calibri", size=10)
    DATA_ALIGNMENT = Alignment(vertical="top", wrap_text=True)
    ALT_ROW_FILL = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")

    # Colori score condizionale
    SCORE_GREEN = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")
    SCORE_YELLOW = PatternFill(start_color="FEF9C3", end_color="FEF9C3", fill_type="solid")
    SCORE_RED = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")

    @staticmethod
    def export_bytes(
        leads: Union[List[Dict], Dict[str, Dict]],
        mode: str = "with_website",
        privacy_policy: WorkspacePrivacyPolicy | None = None,
        suppression_checker: Callable[[Any], bool] | None = None,
        *, origin: RatingFilterGuard | None = None,
    ) -> bytes:
        if origin is not None:
            origin.require_view()
        leads_list = list(leads.values()) if isinstance(leads, dict) else list(leads)
        ExportPolicy.require_exportable(leads_list, mode, privacy_policy, suppression_checker)
        if mode != "with_website":
            raise RuntimeError("Esportazione no_website non consentita.")
        columns = DataExporter._get_website_columns()
        rows = DataExporter._format_website_rows(leads_list)
        wb = Workbook()
        ws = wb.active
        ws.title = "Leads"

        # --- HEADER ROW ---
        for col_idx, col_name in enumerate(columns, 1):
            cell = ws.cell(row=1, column=col_idx, value=col_name)
            cell.font = DataExporter.HEADER_FONT
            cell.fill = DataExporter.HEADER_FILL
            cell.alignment = DataExporter.HEADER_ALIGNMENT
            cell.border = DataExporter.HEADER_BORDER

        # Altezza header
        ws.row_dimensions[1].height = 30

        # --- DATA ROWS ---
        for row_idx, row_data in enumerate(rows, 2):
            for col_idx, value in enumerate(row_data, 1):
                safe_value = sanitize_spreadsheet_value(value)
                cell = ws.cell(row=row_idx, column=col_idx, value=safe_value)
                if is_text_cell(safe_value):
                    cell.data_type = "s"
                cell.font = DataExporter.DATA_FONT
                cell.alignment = DataExporter.DATA_ALIGNMENT

                # Righe alternate
                if row_idx % 2 == 0:
                    cell.fill = DataExporter.ALT_ROW_FILL

            # Colorazione condizionale per Website Score
            if mode == "with_website":
                score_col = columns.index("Website Score") + 1 if "Website Score" in columns else None
                if score_col:
                    score_cell = ws.cell(row=row_idx, column=score_col)
                    try:
                        score_val = int(score_cell.value) if score_cell.value else 0
                        if score_val <= 3:
                            score_cell.fill = DataExporter.SCORE_RED
                        elif score_val <= 6:
                            score_cell.fill = DataExporter.SCORE_YELLOW
                        else:
                            score_cell.fill = DataExporter.SCORE_GREEN
                    except (ValueError, TypeError):
                        pass

        # --- AUTO-FIT COLONNE ---
        col_widths = DataExporter._calculate_column_widths(columns, rows)
        for col_idx, width in enumerate(col_widths, 1):
            col_letter = get_column_letter(col_idx)
            ws.column_dimensions[col_letter].width = width

        # Freeze header row
        ws.freeze_panes = "A2"

        # Auto-filter
        ws.auto_filter.ref = ws.dimensions

        output = BytesIO()
        wb.save(output)
        if origin is not None:
            origin.require_view()
        return output.getvalue()

    @staticmethod
    def export_to_excel(
        leads: Union[List[Dict], Dict[str, Dict]],
        mode: str = "no_website",
        filename: str = "leads_v3_premium.xlsx",
        privacy_policy: WorkspacePrivacyPolicy | None = None,
        suppression_checker: Callable[[Any], bool] | None = None,
        *, origin: RatingFilterGuard | None = None,
    ) -> None:
        if origin is not None:
            origin.require_view()
        if not leads:
            print("[Exporter] Nessun lead da esportare.")
            return
        # Policy rejection stays outside the legacy write-error reporting path.
        data = DataExporter.export_bytes(leads, mode, privacy_policy, suppression_checker, origin=origin)
        destination = Path(filename)
        temporary = None
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            if origin is None:
                destination.write_bytes(data)
            else:
                with tempfile.NamedTemporaryFile(mode='wb', dir=destination.parent,
                                                  prefix='.website-export-', delete=False) as handle:
                    temporary = Path(handle.name)
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                origin.require_view()
                os.replace(temporary, destination)
            print(f"\n[OK] Esportazione premium completata: {len(leads)} lead in '{filename}'")
        except OSError:
            if origin is not None:
                raise OSError('website_export_write_failed') from None
            print("[Errore] Scrittura del file non riuscita. Verifica percorso e permessi.")
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    @staticmethod
    def _get_no_website_columns() -> list:
        return ["Business Name", "Website status", "Provider"]

    @staticmethod
    def _get_website_columns() -> list:
        return [
            "Business Name", "Category", "Website",
            "Extracted Email", "Website Score", "Framework",
            "Diagnosis", "Site Brief", "Cold Message"
        ]

    @staticmethod
    def _format_no_website_rows(leads: List[Dict]) -> List[list]:
        # Presentation-only helper: never used by the Excel export path.
        return [
            [lead.display_name or "N/A", "Senza sito", lead.attribution.label]
            for lead in leads
        ]

    @staticmethod
    def _format_website_rows(leads: List[Dict]) -> List[list]:
        rows = []
        for lead in leads:
            if isinstance(lead, VerifiedLead):
                lead = lead.to_export_record()

            extracted_email = lead.get("extracted_email", "")
            if isinstance(extracted_email, list):
                extracted_email = ", ".join(extracted_email) if extracted_email else ""

            rows.append([
                lead.get("business_name", "N/A"),
                lead.get("category", "N/A"),
                lead.get("website", "N/A"),
                extracted_email or "N/A",
                lead.get("website_score", "N/A"),
                lead.get("framework", "N/A"),
                lead.get("diagnosis", "N/A"),
                lead.get("site_brief", "N/A"),
                lead.get("cold_message", "N/A"),
            ])
        return rows

    @staticmethod
    def _calculate_column_widths(columns: list, rows: list) -> list:
        """Calcola larghezze ottimali per ogni colonna."""
        widths = []
        for col_idx, col_name in enumerate(columns):
            max_len = len(col_name)
            for row in rows:
                if col_idx < len(row):
                    cell_len = len(str(row[col_idx] or ""))
                    max_len = max(max_len, cell_len)

            # Limiti per colonne lunghe (diagnosis, cold_message)
            if col_name in ("Diagnosis", "Cold Message", "Site Brief"):
                widths.append(min(max_len + 2, 50))
            elif col_name in ("Business Summary", "Key Weakness", "Address"):
                widths.append(min(max_len + 2, 40))
            else:
                widths.append(min(max_len + 2, 30))
        return widths
