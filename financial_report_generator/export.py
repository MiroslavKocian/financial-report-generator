"""Build an Excel workbook with summary and grouped-report sheets."""

from io import BytesIO

from openpyxl import Workbook


def build_report_workbook(
    summary: dict[str, object],
    grouped: dict[str, object],
) -> bytes:
    """Return .xlsx bytes: sheet Summary and sheet Grouped."""
    workbook: Workbook = Workbook()
    summary_sheet = workbook.active
    summary_sheet.title = "Summary"
    summary_sheet.append(["metric", "value"])
    summary_sheet.append(["row_count", summary["row_count"]])
    summary_sheet.append(["total_amount", summary["total_amount"]])
    summary_sheet.append(["min_amount", summary["min_amount"]])
    summary_sheet.append(["max_amount", summary["max_amount"]])

    grouped_sheet = workbook.create_sheet("Grouped")
    grouped_sheet.append(["group_by", grouped["group_by"]])
    grouped_sheet.append(
        ["group", "row_count", "total_amount", "min_amount", "max_amount"]
    )
    for row in grouped["groups"]:
        grouped_sheet.append(
            [
                row["group"],
                row["row_count"],
                row["total_amount"],
                row["min_amount"],
                row["max_amount"],
            ]
        )

    buffer: BytesIO = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
