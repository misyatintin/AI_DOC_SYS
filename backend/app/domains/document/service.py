import hashlib
import os
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.domains.extraction.prompt_service import PromptService
from app.domains.extraction.service import ExtractionService
from app.models.document import Document, Extraction


class DocumentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.extraction_service = ExtractionService(db)
        self.prompt_service = PromptService(db)

    async def process_upload(self, file) -> Document:
        payload = await file.read()
        md5_hash = hashlib.md5(payload).hexdigest()
        existing = await self._get_by_hash(md5_hash)
        if existing:
            await self.extraction_service.trigger_extraction(existing)
            await self.db.commit()
            return await self.get_by_id(existing.id)

        _, extension = os.path.splitext(file.filename or "")
        stored_filename = f"{uuid.uuid4()}{extension.lower()}"
        file_path = os.path.join(settings.UPLOAD_DIR, stored_filename)
        with open(file_path, "wb") as output_file:
            output_file.write(payload)

        document = Document(
            filename=file.filename or stored_filename,
            file_path=file_path,
            content_type=file.content_type,
            file_size=len(payload),
            status="pending",
            md5_hash=md5_hash,
        )
        self.db.add(document)
        await self.db.flush()
        await self.extraction_service.trigger_extraction(document)
        await self.db.commit()
        return await self.get_by_id(document.id)

    async def process_bulk_upload(self, files: list) -> list[Document]:
        results: list[Document] = []
        for file in files:
            results.append(await self.process_upload(file))
        return results

    async def get_all(self) -> list[Document]:
        result = await self.db.execute(
            select(Document)
            .options(selectinload(Document.extraction))
            .order_by(Document.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_id(self, doc_id: int) -> Document | None:
        result = await self.db.execute(
            select(Document)
            .options(selectinload(Document.extraction))
            .where(Document.id == doc_id)
        )
        return result.scalar_one_or_none()

    async def delete(self, document: Document) -> int:
        document_id = document.id
        file_path = document.file_path
        await self.db.delete(document)
        await self.db.commit()
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        return document_id

    async def reprocess(self, document: Document) -> Document:
        await self.extraction_service.trigger_extraction(document)
        await self.db.commit()
        return await self.get_by_id(document.id)

    async def apply_correction(self, document: Document, structured_data: dict) -> Document:
        await self.extraction_service.update_extraction(document, structured_data)
        await self.db.commit()
        return await self.get_by_id(document.id)

    async def list_prompts(self):
        prompts = await self.prompt_service.list_versions()
        await self.db.commit()
        return prompts

    async def create_prompt(self, version: str, text: str):
        prompt = await self.prompt_service.create_version(version, text)
        await self.db.commit()
        return prompt

    async def update_prompt(self, prompt_id: int, version: str, text: str):
        prompt = await self.prompt_service.update_version(prompt_id, version, text)
        await self.db.commit()
        return prompt

    async def activate_prompt(self, prompt_id: int):
        prompt = await self.prompt_service.activate_version(prompt_id)
        await self.db.commit()
        return prompt

    async def get_metrics(self) -> dict:
        total_documents = await self.db.scalar(select(func.count(Document.id))) or 0
        completed_documents = (
            await self.db.scalar(select(func.count(Document.id)).where(Document.status == "completed"))
        ) or 0
        failed_documents = (
            await self.db.scalar(select(func.count(Document.id)).where(Document.status == "failed"))
        ) or 0
        review_required = (
            await self.db.scalar(select(func.count(Document.id)).where(Document.status == "review_required"))
        ) or 0
        pending_documents = total_documents - completed_documents - failed_documents - review_required

        averages = await self.db.execute(
            select(
                func.avg(Extraction.processing_time_ms),
                func.avg(Extraction.confidence_score),
            )
        )
        average_processing_time_ms, average_confidence_score = averages.one()

        return {
            "total_documents": total_documents,
            "completed_documents": completed_documents,
            "failed_documents": failed_documents,
            "pending_documents": pending_documents,
            "manual_review_required": review_required,
            "extraction_success_rate": round((completed_documents / total_documents) * 100, 2)
            if total_documents
            else 0.0,
            "average_processing_time_ms": round(float(average_processing_time_ms or 0), 2),
            "average_confidence_score": round(float(average_confidence_score or 0), 2),
        }

    async def _get_by_hash(self, md5_hash: str) -> Document | None:
        result = await self.db.execute(
            select(Document)
            .options(selectinload(Document.extraction))
            .where(Document.md5_hash == md5_hash)
        )
        return result.scalar_one_or_none()
