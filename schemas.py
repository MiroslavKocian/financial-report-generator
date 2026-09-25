"""API response models for OpenAPI documentation."""

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
    total_amount: float
    min_amount: float
    max_amount: float
