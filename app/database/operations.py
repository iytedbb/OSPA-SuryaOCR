"""
Database CRUD operations for SuryaOCR application
"""

import hashlib
import os
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func
from sqlalchemy.exc import IntegrityError

from connection import SessionLocal, logger
from models import (
    Document, DocumentFile, ProcessingJob,
    OCRResult, DetectionResult, SystemStats
)


class DatabaseOperations:
    """
    Main class for all database operations
    """

    def __init__(self):
        self.db: Session = None

    def __enter__(self):
        self.db = SessionLocal()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.db:
            if exc_type:
                self.db.rollback()
            self.db.close()

    # DOCUMENT OPERATIONS

    def create_document(self, metadata: Dict[str, Any]) -> Optional[str]:
        """
        Create a new document with metadata
        Returns document_id if successful, None if failed
        """
        try:
            # Clean metadata (remove empty values)
            clean_metadata = {k: v for k, v in metadata.items() if v not in [None, '', []]}

            # Filter metadata to keep only valid Document model fields
            valid_columns = Document.__table__.columns.keys()
            filtered_metadata = {k: v for k, v in clean_metadata.items() if k in valid_columns}

            document = Document(**filtered_metadata)
            self.db.add(document)
            self.db.commit()
            self.db.refresh(document)

            logger.info(f"Document created: {document.id}")
            return str(document.id)

        except Exception as e:
            logger.error(f"Error creating document: {e}")
            self.db.rollback()
            return None

    def get_document_by_id(self, document_id: str) -> Optional[Document]:
        """
        Get document by ID
        """
        try:
            return self.db.query(Document).filter(Document.id == document_id).first()
        except Exception as e:
            logger.error(f"Error getting document {document_id}: {e}")
            return None

    def search_documents(self, search_params: Dict[str, Any]) -> List[Document]:
        """
        Search documents by various criteria
        """
        try:
            query = self.db.query(Document)

            # Filter by metadata type
            if 'metadata_type' in search_params:
                query = query.filter(Document.metadata_type == search_params['metadata_type'])

            # Search in title
            if 'title' in search_params and search_params['title']:
                query = query.filter(Document.title.ilike(f"%{search_params['title']}%"))

            # Search in author
            if 'author' in search_params and search_params['author']:
                query = query.filter(Document.author.ilike(f"%{search_params['author']}%"))

            # Filter by DOI
            if 'doi' in search_params and search_params['doi']:
                query = query.filter(Document.doi == search_params['doi'])

            # Filter by ISBN
            if 'isbn' in search_params and search_params['isbn']:
                query = query.filter(Document.isbn == search_params['isbn'])

            return query.order_by(desc(Document.created_at)).limit(50).all()

        except Exception as e:
            logger.error(f"Error searching documents: {e}")
            return []

    def check_duplicate_by_metadata(self, metadata: Dict[str, Any]) -> Optional[Document]:
        """
        Check if document already exists based on key metadata fields
        (GÜNCELLENDİ: Daha granüler kontrol)
        """
        try:
            query = self.db.query(Document)

            # Check by DOI first (most reliable)
            if metadata.get('doi'):
                existing = query.filter(Document.doi == metadata['doi']).first()
                if existing:
                    return existing

            # Check by ISBN for books
            if metadata.get('isbn') and metadata.get('metadata_type') == 'book':
                existing = query.filter(
                    and_(
                        Document.isbn == metadata['isbn'],
                        Document.metadata_type == 'book'
                    )
                ).first()
                if existing:
                    return existing

            # Check by title + author + publisher + editor + year combination
            if metadata.get('title') and metadata.get('author'):
                base_filters = [
                    Document.title == metadata['title'],
                    Document.author == metadata['author'],
                    Document.metadata_type == metadata.get('metadata_type', 'article')
                ]


                base_filters.append(Document.publisher == metadata.get('publisher'))
                base_filters.append(Document.editor == metadata.get('editor'))
                base_filters.append(Document.volume == metadata.get('volume'))
                base_filters.append(Document.edition == metadata.get('edition'))

                # Yayın yılını da kontrol et (modellerde mevcut)
                base_filters.append(Document.publication_year == metadata.get('publication_year'))

                existing = query.filter(and_(*base_filters)).first()
                if existing:
                    return existing

            return None

        except Exception as e:
            logger.error(f"Error checking duplicate: {e}")
            return None

    # FILE OPERATIONS

    def add_file_to_document(self, document_id: str, file_info: Dict[str, Any]) -> Optional[str]:
        """
        Add a file to document
        """
        try:
            # Calculate file hash
            file_hash = self.calculate_file_hash(file_info['file_path'])

            # Check if file already exists
            existing_file = self.db.query(DocumentFile).filter(
                and_(
                    DocumentFile.file_hash == file_hash,
                    DocumentFile.file_type == file_info['file_type']
                )
            ).first()

            if existing_file:
                logger.info(f"File already exists: {existing_file.id}")
                return str(existing_file.id)

            # Create new file record
            document_file = DocumentFile(
                document_id=document_id,
                filename=file_info['filename'],
                original_filename=file_info['original_filename'],
                file_path=file_info['file_path'],
                file_size=file_info['file_size'],
                mime_type=file_info['mime_type'],
                file_type=file_info['file_type'],
                file_hash=file_hash
            )

            self.db.add(document_file)
            self.db.commit()
            self.db.refresh(document_file)

            logger.info(f"File added: {document_file.id}")
            return str(document_file.id)

        except Exception as e:
            logger.error(f"Error adding file: {e}")
            self.db.rollback()
            return None

    def get_document_files(self, document_id: str, file_type: Optional[str] = None) -> List[DocumentFile]:
        """
        Get all files for a document
        """
        try:
            query = self.db.query(DocumentFile).filter(DocumentFile.document_id == document_id)

            if file_type:
                query = query.filter(DocumentFile.file_type == file_type)

            return query.all()

        except Exception as e:
            logger.error(f"Error getting document files: {e}")
            return []

    def check_file_exists_by_hash(self, file_path: str, file_type: str) -> Optional[DocumentFile]:
        """
        Check if file already exists by hash
        """
        try:
            file_hash = self.calculate_file_hash(file_path)
            return self.db.query(DocumentFile).filter(
                and_(
                    DocumentFile.file_hash == file_hash,
                    DocumentFile.file_type == file_type
                )
            ).first()
        except Exception as e:
            logger.error(f"Error checking file hash: {e}")
            return None

    # PROCESSING JOB OPERATIONS

    def create_processing_job(self, document_id: str, process_mode: str, output_formats: List[str]) -> Optional[str]:
        """
        Create a new processing job
        """
        try:
            job = ProcessingJob(
                document_id=document_id,
                process_mode=process_mode,
                output_formats=list(map(str, output_formats)) if output_formats else [], # Explicitly cast to list of strings
                status='pending'
            )

            self.db.add(job)
            self.db.commit()
            self.db.refresh(job)

            logger.info(f"Processing job created: {job.id}")
            return str(job.id)

        except Exception as e:
            logger.error(f"Error creating processing job: {e}")
            self.db.rollback()
            return None

    def update_job_status(self, job_id: str, status: str, **kwargs) -> bool:
        """
        Update processing job status and other fields
        """
        try:
            job = self.db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
            if not job:
                return False

            job.status = status

            # Update additional fields
            for key, value in kwargs.items():
                if hasattr(job, key):
                    setattr(job, key, value)

            if status == 'processing' and not job.started_at:
                job.started_at = datetime.now()
            elif status in ['completed', 'failed', 'cancelled'] and not job.completed_at:
                job.completed_at = datetime.now()
                if job.started_at:
                    processing_time = (job.completed_at - job.started_at).total_seconds()
                    job.processing_time_seconds = processing_time

            self.db.commit()
            return True

        except Exception as e:
            logger.error(f"Error updating job status: {e}")
            self.db.rollback()
            return False

    def get_processing_job(self, job_id: str) -> Optional[ProcessingJob]:
        """
        Get processing job by ID
        """
        try:
            return self.db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        except Exception as e:
            logger.error(f"Error getting processing job: {e}")
            return None

    def get_active_jobs(self) -> List[ProcessingJob]:
        """
        Get all active (processing) jobs
        """
        try:
            return self.db.query(ProcessingJob).filter(
                ProcessingJob.status == 'processing'
            ).all()
        except Exception as e:
            logger.error(f"Error getting active jobs: {e}")
            return []

    # OCR RESULTS OPERATIONS

    def save_ocr_results(self, job_id: str, document_id: str, results: Dict[str, Any]) -> Optional[str]:
        """
        Save OCR processing results
        """
        try:
            ocr_result = OCRResult(
                document_id=document_id,
                processing_job_id=job_id,
                markdown_content=results.get('markdown_content'),
                xml_content=results.get('xml_content'),
                total_pages=results.get('total_pages', 0),
                total_characters=results.get('total_characters'),
                confidence_score=results.get('confidence_score'),
                processing_time_seconds=results.get('processing_time_seconds'),
                characters_per_second=results.get('characters_per_second')
            )

            self.db.add(ocr_result)
            self.db.commit()
            self.db.refresh(ocr_result)

            logger.info(f"OCR results saved: {ocr_result.id}")
            return str(ocr_result.id)

        except Exception as e:
            logger.error(f"Error saving OCR results: {e}")
            self.db.rollback()
            return None

    def get_ocr_results_by_document(self, document_id: str) -> Optional[OCRResult]:
        """
        Get latest OCR results for a document
        """
        try:
            return self.db.query(OCRResult).filter(
                OCRResult.document_id == document_id
            ).order_by(desc(OCRResult.created_at)).first()
        except Exception as e:
            logger.error(f"Error getting OCR results: {e}")
            return None

    # DETECTION RESULTS OPERATIONS

    def save_detection_results(self, job_id: str, document_id: str, page_results: List[Dict[str, Any]]) -> bool:
        """
        Save detection results for all pages
        """
        try:
            for page_data in page_results:
                detection_result = DetectionResult(
                    document_id=document_id,
                    processing_job_id=job_id,
                    page_number=page_data['page_number'],
                    total_pages=page_data['total_pages'],
                    text_regions=page_data['text_regions'],
                    region_count=page_data['region_count'],
                    average_confidence=page_data.get('average_confidence'),
                    processing_time_ms=page_data.get('processing_time_ms')
                )
                self.db.add(detection_result)

            self.db.commit()
            logger.info(f"Detection results saved for {len(page_results)} pages")
            return True

        except Exception as e:
            logger.error(f"Error saving detection results: {e}")
            self.db.rollback()
            return False

    def get_detection_results_by_document(self, document_id: str) -> List[DetectionResult]:
        """
        Get detection results for a document
        """
        try:
            return self.db.query(DetectionResult).filter(
                DetectionResult.document_id == document_id
            ).order_by(DetectionResult.page_number).all()
        except Exception as e:
            logger.error(f"Error getting detection results: {e}")
            return []

    # STATISTICS OPERATIONS

    def update_daily_stats(self, stat_date: date = None) -> bool:
        """
        Update daily statistics
        """
        try:
            if not stat_date:
                stat_date = date.today()

            # Get existing stats or create new
            stats = self.db.query(SystemStats).filter(SystemStats.stat_date == stat_date).first()
            if not stats:
                stats = SystemStats(stat_date=stat_date)
                self.db.add(stats)

            # Calculate statistics for the day
            completed_jobs = self.db.query(ProcessingJob).filter(
                and_(
                    ProcessingJob.status == 'completed',
                    func.date(ProcessingJob.completed_at) == stat_date
                )
            ).all()

            failed_jobs = self.db.query(ProcessingJob).filter(
                and_(
                    ProcessingJob.status == 'failed',
                    func.date(ProcessingJob.completed_at) == stat_date
                )
            ).count()

            # Update statistics
            stats.documents_processed = len(completed_jobs)
            stats.total_pages_processed = sum(job.total_pages or 0 for job in completed_jobs)
            stats.total_processing_time_seconds = sum(
                int(job.processing_time_seconds or 0) for job in completed_jobs
            )
            stats.failed_jobs = failed_jobs

            if len(completed_jobs) > 0:
                stats.avg_processing_time_per_page = (
                        stats.total_processing_time_seconds / max(stats.total_pages_processed, 1)
                )
                stats.error_rate = failed_jobs / (len(completed_jobs) + failed_jobs)

            self.db.commit()
            return True

        except Exception as e:
            logger.error(f"Error updating daily stats: {e}")
            self.db.rollback()
            return False

    # UTILITY METHODS

    def calculate_file_hash(self, file_path: str) -> str:
        """
        Calculate SHA-256 hash of file
        """
        try:
            hash_sha256 = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating file hash: {e}")
            return ""

    def get_database_stats(self) -> Dict[str, int]:
        """
        Get general database statistics
        """
        try:
            stats = {
                'total_documents': self.db.query(Document).count(),
                'total_files': self.db.query(DocumentFile).count(),
                'processing_jobs': self.db.query(ProcessingJob).count(),
                'completed_jobs': self.db.query(ProcessingJob).filter(
                    ProcessingJob.status == 'completed'
                ).count(),
                'failed_jobs': self.db.query(ProcessingJob).filter(
                    ProcessingJob.status == 'failed'
                ).count(),
                'active_jobs': self.db.query(ProcessingJob).filter(
                    ProcessingJob.status == 'processing'
                ).count()
            }
            return stats
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {}

    def cleanup_old_data(self, days_old: int = 30) -> bool:
        """
        Clean up old temporary data
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days_old)

            # Delete old failed jobs
            old_failed_jobs = self.db.query(ProcessingJob).filter(
                and_(
                    ProcessingJob.status == 'failed',
                    ProcessingJob.created_at < cutoff_date
                )
            ).delete()

            logger.info(f"Cleaned up {old_failed_jobs} old failed jobs")
            self.db.commit()
            return True

        except Exception as e:
            logger.error(f"Error cleaning up old data: {e}")
            self.db.rollback()
            return False


# Convenience functions for quick operations
def create_document_with_context(metadata: Dict[str, Any]) -> Optional[str]:
    """
    Create document using context manager
    """
    with DatabaseOperations() as db_ops:
        return db_ops.create_document(metadata)


def search_documents_with_context(search_params: Dict[str, Any]) -> List[Document]:
    """
    Search documents using context manager
    """
    with DatabaseOperations() as db_ops:
        return db_ops.search_documents(search_params)


def get_document_with_context(document_id: str) -> Optional[Document]:
    """
    Get document using context manager
    """
    with DatabaseOperations() as db_ops:
        return db_ops.get_document_by_id(document_id)