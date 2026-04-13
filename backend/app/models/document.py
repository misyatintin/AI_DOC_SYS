from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.session import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    content_type = Column(String(255), nullable=True)
    file_size = Column(Integer, nullable=True)
    status = Column(String(50), default="pending", nullable=False)
    error_message = Column(Text, nullable=True)
    md5_hash = Column(String(32), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    extraction = relationship(
        "Extraction",
        back_populates="document",
        uselist=False,
        cascade="all, delete-orphan",
    )


class Extraction(Base):
    __tablename__ = "extractions"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), unique=True, nullable=False)
    raw_text = Column(Text, nullable=True)
    raw_json = Column(JSON, nullable=True)
    structured_data = Column(JSON, nullable=False)
    confidence_score = Column(Float, nullable=False, default=0.0)
    validation_errors = Column(JSON, nullable=False, default=list)
    missing_fields = Column(JSON, nullable=False, default=list)
    processing_time_ms = Column(Integer, nullable=False, default=0)
    prompt_version = Column(String(50), nullable=False)
    manually_corrected = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    document = relationship("Document", back_populates="extraction")


class PromptVersion(Base):
    __tablename__ = "prompt_versions"

    id = Column(Integer, primary_key=True, index=True)
    version = Column(String(50), unique=True, nullable=False)
    prompt_text = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
