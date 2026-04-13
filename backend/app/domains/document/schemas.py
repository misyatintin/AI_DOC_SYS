from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class LineItemSchema(BaseModel):
    description: str = ""
    quantity: float = 0
    unit_price: float = 0
    line_total: float = 0


class StructuredInvoiceSchema(BaseModel):
    vendor_name: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    currency: str | None = None
    total_amount: float | None = None
    tax_amount: float | None = None
    line_items: list[LineItemSchema] = Field(default_factory=list)


class ExtractionSchema(BaseModel):
    id: int
    structured_data: StructuredInvoiceSchema
    confidence_score: float
    validation_errors: list[str]
    missing_fields: list[str]
    processing_time_ms: int
    prompt_version: str
    manually_corrected: bool

    class Config:
        from_attributes = True


class DocumentSchema(BaseModel):
    id: int
    filename: str
    status: str
    content_type: str | None = None
    file_size: int | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    extraction: ExtractionSchema | None = None

    class Config:
        from_attributes = True


class DocumentDetailSchema(DocumentSchema):
    file_path: str


class CorrectionUpdate(BaseModel):
    structured_data: StructuredInvoiceSchema | dict[str, Any]


class PromptVersionCreate(BaseModel):
    version: str
    prompt_text: str


class PromptVersionUpdate(BaseModel):
    version: str
    prompt_text: str


class PromptVersionSchema(BaseModel):
    id: int
    version: str
    prompt_text: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class DeleteDocumentResponse(BaseModel):
    id: int
    deleted: bool = True


class MetricsOverviewSchema(BaseModel):
    total_documents: int
    completed_documents: int
    failed_documents: int
    pending_documents: int
    manual_review_required: int
    extraction_success_rate: float
    average_processing_time_ms: float
    average_confidence_score: float
