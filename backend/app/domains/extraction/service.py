import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.extraction.prompt_service import PromptService
from app.models.document import Document, Extraction
from app.services.extraction_service import AIService, ValidationService


class ExtractionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.prompt_service = PromptService(db)

    async def trigger_extraction(self, document: Document) -> Extraction | None:
        document.status = "processing"
        document.error_message = None
        await self.db.flush()

        started_at = time.perf_counter()
        try:
            prompt = await self.prompt_service.ensure_default_prompt()
            text = await AIService.extract_text_from_pdf(document.file_path)
            extracted_data, metadata = await AIService.extract_structured_data(
                text,
                prompt.prompt_text,
                document.file_path,
            )
            validation = ValidationService.validate_invoice(extracted_data)
            processing_time_ms = int((time.perf_counter() - started_at) * 1000)

            extraction = await self._get_or_create_extraction(document.id)
            extraction.raw_text = text
            extraction.raw_json = {
                "provider": metadata.get("provider"),
                "model": metadata.get("model"),
                "attempts": metadata.get("attempts", []),
                "raw_extracted_data": extracted_data,
            }
            extraction.structured_data = validation["normalized_data"]
            extraction.confidence_score = validation["confidence_score"]
            extraction.validation_errors = validation["errors"]
            extraction.missing_fields = validation["missing_fields"]
            extraction.processing_time_ms = processing_time_ms
            extraction.prompt_version = prompt.version
            extraction.manually_corrected = False

            document.status = "completed" if not validation["missing_fields"] else "review_required"
            await self.db.flush()
            return extraction
        except Exception as exc:
            document.status = "failed"
            document.error_message = str(exc)
            await self.db.flush()
            return None

    async def update_extraction(self, document: Document, updated_data: dict) -> Extraction | None:
        extraction = await self._get_or_create_extraction(document.id)
        validation = ValidationService.validate_invoice(updated_data)
        extraction.structured_data = validation["normalized_data"]
        extraction.confidence_score = validation["confidence_score"]
        extraction.validation_errors = validation["errors"]
        extraction.missing_fields = validation["missing_fields"]
        extraction.manually_corrected = True
        document.status = "completed" if not validation["missing_fields"] else "review_required"
        document.error_message = None
        await self.db.flush()
        return extraction

    async def _get_or_create_extraction(self, document_id: int) -> Extraction:
        result = await self.db.execute(select(Extraction).where(Extraction.document_id == document_id))
        extraction = result.scalar_one_or_none()
        if extraction:
            return extraction

        extraction = Extraction(
            document_id=document_id,
            raw_json={},
            structured_data={},
            validation_errors=[],
            missing_fields=[],
            prompt_version="v1.0",
        )
        self.db.add(extraction)
        await self.db.flush()
        return extraction
