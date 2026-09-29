"""API response models for OpenAPI documentation.

Money fields are strings with two decimal places so JSON does not
reintroduce binary floats.
"""

from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    """JSON body returned after a successful upload."""

    filename: str
    file_id: int = Field(description="Primary key in the uploads table.")
    rows_stored: int
    status: str


class SummaryResponse(BaseModel):
    """JSON sales summary report."""

    row_count: int
    total_amount: str
    min_amount: str
    max_amount: str


class GroupRow(BaseModel):
    """Totals for one group in a grouped report."""

    group: str
    row_count: int
    total_amount: str
    min_amount: str
    max_amount: str


class GroupedReportResponse(BaseModel):
    """JSON report grouped by one stored column."""

    group_by: str
    row_count: int
    total_amount: str
    groups: list[GroupRow]
