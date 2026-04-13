import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


load_dotenv()


class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Document Intelligence System"
    API_PREFIX: str = "/api"
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "mysql+aiomysql://root:new_password@localhost/ai_doc_sys",
    )
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")
    EXTRACTION_PROVIDER: str = os.getenv("EXTRACTION_PROVIDER", "auto")
    OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-5-mini")
    OPENAI_TIMEOUT_SECONDS: int = int(os.getenv("OPENAI_TIMEOUT_SECONDS", "120"))
    GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    PROMPT_VERSION: str = os.getenv("PROMPT_VERSION", "v2.0-openai-pdf")
    TOTAL_TOLERANCE: float = float(os.getenv("TOTAL_TOLERANCE", "0.05"))
    LLM_TEXT_LIMIT: int = int(os.getenv("LLM_TEXT_LIMIT", "12000"))
    MAX_TABLES_FOR_LLM: int = int(os.getenv("MAX_TABLES_FOR_LLM", "6"))
    MAX_ROWS_PER_TABLE: int = int(os.getenv("MAX_ROWS_PER_TABLE", "12"))
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    DEFAULT_PROMPT_TEXT: str = (
        "You are an enterprise invoice extraction system. Extract structured invoice data from the PDF. "
        "Use the PDF as the source of truth, and use OCR text only as supporting context. "
        "Return vendor_name, invoice_number, invoice_date, currency, total_amount, tax_amount, and line_items. "
        "For line_items, include only billed rows and exclude subtotal, tax, total, discounts, payment rows, or bank details. "
        "If a value is not present, return null instead of inventing one. Return strict JSON only."
    )

    model_config = SettingsConfigDict(case_sensitive=True)


settings = Settings()

Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
