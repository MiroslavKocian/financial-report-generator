"""Build an Excel workbook with the sales summary."""

from io import BytesIO

from openpyxl import Workbook


def build_report_workbook(summary: dict[str, object]) -> bytes:
    """Return .xlsx bytes with a single Summary sheet."""
    workbook: Workbook = Workbook()
    summary_sheet = workbook.active
    summary_sheet.title = "Summary"
    summary_sheet.append(["metric", "value"])
    summary_sheet.append(["row_count", summary["row_count"]])
    summary_sheet.append(["total_amount", summary["total_amount"]])
    summary_sheet.append(["min_amount", summary["min_amount"]])
    summary_sheet.append(["max_amount", summary["max_amount"]])

    buffer: BytesIO = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
