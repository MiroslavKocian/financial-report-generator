"""The committed example workbook matches the documented sample totals."""

from pathlib import Path

from financial_report_generator.analysis import grouped_sales, summarize_sales
from financial_report_generator.excel_loader import load_excel_dataframe

SAMPLE_PATH = Path(__file__).resolve().parent.parent / "examples" / "sales_example.xlsx"


def test_sales_example_workbook() -> None:
    frame = load_excel_dataframe(str(SAMPLE_PATH))
    summary = summarize_sales(frame)
    assert summary["row_count"] == 4
    assert summary["total_amount"] == "41.00"
    assert summary["min_amount"] == "1.00"
    assert summary["max_amount"] == "25.00"

    by_region = grouped_sales(frame)
    assert by_region["group_by"] == "region"
    assert by_region["total_amount"] == "41.00"
    groups = {row["group"]: row["total_amount"] for row in by_region["groups"]}
    assert groups == {"North": "11.00", "South": "30.00"}

    by_product = grouped_sales(frame, group_by="product")
    assert by_product["group_by"] == "product"
    product_groups = {
        row["group"]: row["total_amount"] for row in by_product["groups"]
    }
    assert product_groups == {"A": "35.00", "B": "6.00"}
