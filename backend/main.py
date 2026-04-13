from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.schema_repair import reconcile_schema
from app.db.session import Base, engine
from app.domains.document.router import router as document_router
from app.domains.extraction.prompt_service import PromptService
from app.db.session import async_session


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await reconcile_schema(connection)

    async with async_session() as session:
        prompt_service = PromptService(session)
        await prompt_service.ensure_default_prompt()
        await session.commit()

    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Invoice ingestion, extraction, validation and review system.",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(document_router, prefix=settings.API_PREFIX)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "ai-document-intelligence-system"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
