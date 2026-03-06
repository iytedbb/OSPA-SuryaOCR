"""
SQLAlchemy models for SuryaOCR application
"""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Text, DateTime, Boolean,
    DECIMAL, BIGINT, Date, ForeignKey, ARRAY, CheckConstraint,
    UniqueConstraint, Index, text, JSON
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.orm import declarative_base
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

# Create Base instance for this module
Base = declarative_base()

class GUID(TypeDecorator):
    """Platform-independent GUID type."""
    impl = CHAR
    cache_ok = True
    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(CHAR(36))
    def process_bind_param(self, value, dialect):
        if value is None: return value
        return str(value)
    def process_result_value(self, value, dialect):
        if value is None: return value
        if not isinstance(value, uuid.UUID):
            return uuid.UUID(value)
        return value


class Document(Base):
    """
    Main documents table storing metadata for all document types
    """
    __tablename__ = 'documents'

    # Primary key
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)

    # Basic document info
    title = Column(String(1000), nullable=False)
    metadata_type = Column(String(20), nullable=False)
    citation_style = Column(String(10), default='apa')

    # Common fields for all types
    author = Column(Text)
    language = Column(String(10), default='tr')
    publication_year = Column(Integer)
    pages = Column(String(50))
    url = Column(Text)

    # Book specific fields
    editor = Column(Text)
    publisher = Column(Text)
    publication_city = Column(Text)
    country = Column(Text)
    edition = Column(Text)
    volume = Column(Text)
    series = Column(Text)
    page_count = Column(Integer)
    isbn = Column(String(20))

    # Article specific fields
    publication = Column(Text)  # Journal/Magazine name
    issue = Column(Text)
    doi = Column(String(100))
    issn = Column(String(20))
    journal_abbreviation = Column(Text)
    series_title = Column(Text)
    series_text = Column(Text)

    # Newspaper specific fields (Gazete için özel alanlar)
    newspaper_name = Column(Text)  # Gazete adı (örn: "Cumhuriyet")
    publication_place = Column(Text)  # Yayın yeri (örn: "İstanbul")
    section = Column(Text)  # Bölüm (örn: "Spor", "Ekonomi")
    column_name = Column(Text)  # Köşe adı
    page_range = Column(String(50))  # Sayfa aralığı (örn: "1-4")

    # Encyclopedia specific fields
    encyclopedia_title = Column(Text)
    short_title = Column(Text)
    access_date = Column(Date)

    # Archive and library fields (common)
    archive = Column(Text)
    archive_location = Column(Text)
    library_catalog = Column(Text)
    call_number = Column(Text)
    rights = Column(Text)

    # Date fields
    date = Column(Date)
    created_at = Column(DateTime, default=func.current_timestamp())
    updated_at = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())

    # Relationships
    files = relationship("DocumentFile", back_populates="document", cascade="all, delete-orphan")
    processing_jobs = relationship("ProcessingJob", back_populates="document", cascade="all, delete-orphan")
    ocr_results = relationship("OCRResult", back_populates="document", cascade="all, delete-orphan")
    detection_results = relationship("DetectionResult", back_populates="document", cascade="all, delete-orphan")

    # Constraints
    __table_args__ = (
        CheckConstraint("metadata_type IN ('book', 'article', 'encyclopedia', 'newspaper')",
                        name='check_metadata_type'),
        CheckConstraint("citation_style IN ('apa', 'chicago')", name='check_citation_style'),
        Index('idx_documents_metadata_type', 'metadata_type'),
        Index('idx_documents_created_at', 'created_at'),
    )

    def __repr__(self):
        return f"<Document(id={self.id}, title='{self.title[:50]}...', type='{self.metadata_type}')>"


class DocumentFile(Base):
    """
    File storage table tracking all files related to documents
    """
    __tablename__ = 'document_files'

    # Primary key
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    document_id = Column(GUID(), ForeignKey('documents.id', ondelete='CASCADE'))

    # File information
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(Text, nullable=False)
    file_size = Column(BIGINT, nullable=False)
    mime_type = Column(String(100), nullable=False)
    file_type = Column(String(20), nullable=False)

    # File hash for duplicate detection
    file_hash = Column(String(64), nullable=False)

    # Metadata
    created_at = Column(DateTime, default=func.current_timestamp())

    # Relationships
    document = relationship("Document", back_populates="files")

    # Constraints
    __table_args__ = (
        CheckConstraint("file_type IN ('pdf', 'image', 'md', 'xml')", name='check_file_type'),
        UniqueConstraint('file_hash', 'file_type', name='unique_file_hash_type'),
        Index('idx_document_files_document_id', 'document_id'),
        Index('idx_document_files_type', 'file_type'),
        Index('idx_document_files_hash', 'file_hash'),
    )

    def __repr__(self):
        return f"<DocumentFile(id={self.id}, filename='{self.filename}', type='{self.file_type}')>"


class ProcessingJob(Base):
    """
    Processing jobs table tracking OCR processing status
    """
    __tablename__ = 'processing_jobs'

    # Primary key
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    document_id = Column(GUID(), ForeignKey('documents.id', ondelete='CASCADE'))

    # Job details
    process_mode = Column(String(20), nullable=False)
    output_formats = Column(JSON)  # Database has this as JSON type
    status = Column(String(20), default='pending')

    # Progress tracking
    total_pages = Column(Integer, default=0)
    current_page = Column(Integer, default=0)
    progress_percent = Column(DECIMAL(5,2), default=0.00)

    # Timing
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    processing_time_seconds = Column(DECIMAL(8,2))

    # Error handling
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)

    # Metadata
    created_at = Column(DateTime, default=func.current_timestamp())
    updated_at = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())

    # Relationships
    document = relationship("Document", back_populates="processing_jobs")
    ocr_results = relationship("OCRResult", back_populates="processing_job", cascade="all, delete-orphan")
    detection_results = relationship("DetectionResult", back_populates="processing_job", cascade="all, delete-orphan")

    # Constraints
    __table_args__ = (
        CheckConstraint("process_mode IN ('ocr', 'detection')", name='check_process_mode'),
        CheckConstraint("status IN ('pending', 'processing', 'completed', 'failed', 'cancelled')", name='check_status'),
        Index('idx_processing_jobs_status', 'status'),
        Index('idx_processing_jobs_created_at', 'created_at'),
        Index('idx_processing_jobs_document_id', 'document_id'),
    )

    def __repr__(self):
        return f"<ProcessingJob(id={self.id}, mode='{self.process_mode}', status='{self.status}')>"


class OCRResult(Base):
    """
    OCR results table storing processed content
    """
    __tablename__ = 'ocr_results'

    # Primary key
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    document_id = Column(GUID(), ForeignKey('documents.id', ondelete='CASCADE'))
    processing_job_id = Column(GUID(), ForeignKey('processing_jobs.id', ondelete='CASCADE'))

    # Content storage
    markdown_content = Column(Text)
    xml_content = Column(Text)

    # Processing metadata
    total_pages = Column(Integer, nullable=False)
    total_characters = Column(Integer)
    confidence_score = Column(DECIMAL(5,4))  # Average confidence score

    # Performance metrics
    processing_time_seconds = Column(DECIMAL(8,2))
    characters_per_second = Column(DECIMAL(10,2))

    # Metadata
    created_at = Column(DateTime, default=func.current_timestamp())

    # Relationships
    document = relationship("Document", back_populates="ocr_results")
    processing_job = relationship("ProcessingJob", back_populates="ocr_results")

    # Indexes
    __table_args__ = (
        Index('idx_ocr_results_document_id', 'document_id'),
    )

    def __repr__(self):
        return f"<OCRResult(id={self.id}, pages={self.total_pages}, chars={self.total_characters})>"


class DetectionResult(Base):
    """
    Detection results table storing text detection data
    """
    __tablename__ = 'detection_results'

    # Primary key
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    document_id = Column(GUID(), ForeignKey('documents.id', ondelete='CASCADE'))
    processing_job_id = Column(GUID(), ForeignKey('processing_jobs.id', ondelete='CASCADE'))

    # Page information
    page_number = Column(Integer, nullable=False)
    total_pages = Column(Integer, nullable=False)

    # Detection data (stored as JSON for flexibility)
    text_regions = Column(JSON, nullable=False)
    region_count = Column(Integer, nullable=False)

    # Page-level statistics
    average_confidence = Column(DECIMAL(5,4))
    processing_time_ms = Column(Integer)

    # Metadata
    created_at = Column(DateTime, default=func.current_timestamp())

    # Relationships
    document = relationship("Document", back_populates="detection_results")
    processing_job = relationship("ProcessingJob", back_populates="detection_results")

    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint('processing_job_id', 'page_number', name='unique_job_page'),
        Index('idx_detection_results_document_id', 'document_id'),
        Index('idx_detection_results_job_page', 'processing_job_id', 'page_number'),
    )

    def __repr__(self):
        return f"<DetectionResult(id={self.id}, page={self.page_number}, regions={self.region_count})>"


class SystemStats(Base):
    """
    System statistics table tracking usage and performance
    """
    __tablename__ = 'system_stats'

    # Primary key
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)

    # Daily aggregation key
    stat_date = Column(Date, nullable=False)

    # Usage metrics
    documents_processed = Column(Integer, default=0)
    total_pages_processed = Column(Integer, default=0)
    total_processing_time_seconds = Column(BIGINT, default=0)

    # File metrics
    total_file_size_mb = Column(BIGINT, default=0)
    avg_file_size_mb = Column(DECIMAL(8,2), default=0)

    # Performance metrics
    avg_processing_time_per_page = Column(DECIMAL(8,2), default=0)
    avg_confidence_score = Column(DECIMAL(5,4), default=0)

    # Error tracking
    failed_jobs = Column(Integer, default=0)
    error_rate = Column(DECIMAL(5,4), default=0)

    # Metadata
    created_at = Column(DateTime, default=func.current_timestamp())
    updated_at = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())

    # Constraints
    __table_args__ = (
        UniqueConstraint('stat_date', name='unique_stat_date'),
        Index('idx_system_stats_date', 'stat_date'),
    )

    def __repr__(self):
        return f"<SystemStats(date={self.stat_date}, docs={self.documents_processed})>"

