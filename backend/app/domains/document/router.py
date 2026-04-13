from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.domains.document.schemas import (
    CorrectionUpdate,
    DeleteDocumentResponse,
    DocumentDetailSchema,
    DocumentSchema,
    MetricsOverviewSchema,
    PromptVersionCreate,
    PromptVersionUpdate,
    PromptVersionSchema,
)
from app.domains.document.service import DocumentService


router = APIRouter(tags=["Document Intelligence"])


@router.post("/documents", response_model=DocumentSchema)
async def upload_invoice(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    service = DocumentService(db)
    return await service.process_upload(file)


@router.post("/documents/bulk", response_model=list[DocumentSchema])
async def upload_invoices(files: list[UploadFile] = File(...), db: AsyncSession = Depends(get_db)):
    service = DocumentService(db)
    return await service.process_bulk_upload(files)


@router.get("/documents", response_model=list[DocumentSchema])
async def list_invoices(db: AsyncSession = Depends(get_db)):
    service = DocumentService(db)
    return await service.get_all()


@router.get("/documents/{document_id}", response_model=DocumentDetailSchema)
async def get_invoice(document_id: int, db: AsyncSession = Depends(get_db)):
    service = DocumentService(db)
    document = await service.get_by_id(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return document


@router.get("/documents/{document_id}/file")
async def get_invoice_file(document_id: int, db: AsyncSession = Depends(get_db)):
    service = DocumentService(db)
    document = await service.get_by_id(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return FileResponse(
        document.file_path,
        media_type=document.content_type or "application/pdf",
        filename=document.filename,
        content_disposition_type="inline",
    )


@router.post("/reprocess/{document_id}", response_model=DocumentSchema)
async def reprocess_invoice(document_id: int, db: AsyncSession = Depends(get_db)):
    service = DocumentService(db)
    document = await service.get_by_id(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return await service.reprocess(document)


@router.patch("/documents/{document_id}/correction", response_model=DocumentSchema)
async def manual_correction(
    document_id: int,
    update: CorrectionUpdate,
    db: AsyncSession = Depends(get_db),
):
    service = DocumentService(db)
    document = await service.get_by_id(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Invoice not found")
    structured_data = (
        update.structured_data.model_dump()
        if hasattr(update.structured_data, "model_dump")
        else update.structured_data
    )
    return await service.apply_correction(document, structured_data)


@router.delete("/documents/{document_id}", response_model=DeleteDocumentResponse)
async def delete_invoice(document_id: int, db: AsyncSession = Depends(get_db)):
    service = DocumentService(db)
    document = await service.get_by_id(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Invoice not found")
    deleted_id = await service.delete(document)
    return DeleteDocumentResponse(id=deleted_id)


@router.get("/metrics/overview", response_model=MetricsOverviewSchema)
async def metrics_overview(db: AsyncSession = Depends(get_db)):
    service = DocumentService(db)
    return await service.get_metrics()


@router.get("/prompts", response_model=list[PromptVersionSchema])
async def list_prompt_versions(db: AsyncSession = Depends(get_db)):
    service = DocumentService(db)
    return await service.list_prompts()


@router.post("/prompts", response_model=PromptVersionSchema)
async def create_prompt_version(payload: PromptVersionCreate, db: AsyncSession = Depends(get_db)):
    service = DocumentService(db)
    return await service.create_prompt(payload.version, payload.prompt_text)


@router.put("/prompts/{prompt_id}", response_model=PromptVersionSchema)
async def update_prompt_version(
    prompt_id: int,
    payload: PromptVersionUpdate,
    db: AsyncSession = Depends(get_db),
):
    service = DocumentService(db)
    prompt = await service.update_prompt(prompt_id, payload.version, payload.prompt_text)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt version not found")
    return prompt


@router.post("/prompts/{prompt_id}/activate", response_model=PromptVersionSchema)
async def activate_prompt_version(prompt_id: int, db: AsyncSession = Depends(get_db)):
    service = DocumentService(db)
    prompt = await service.activate_prompt(prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt version not found")
    return prompt
