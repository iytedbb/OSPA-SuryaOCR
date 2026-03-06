"""
Database Service Module for SuryaOCR Backend Integration
"""

import os
import hashlib
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import logging

import shutil
import uuid

from operations import DatabaseOperations
from connection import initialize_database, logger as db_logger


class DatabaseService:
    """
    SuryaOCR Backend için temiz database interface
    """

    def __init__(self, auto_init: bool = True):
        """
        Database service'i başlat
        """
        self.logger = logging.getLogger(__name__)
        self._initialized = False

        # ✅ Kalıcı depolama yollarını tanımla
        try:
            # Ana 'veriler' klasörü (app/database -> app -> repo_root -> data/veriler)
            base_storage_dir = Path(__file__).resolve().parent.parent.parent / "data" / "veriler"

            # Alt klasörler
            self.pdf_storage_dir = base_storage_dir / "pdf"
            self.image_storage_dir = base_storage_dir / "images"

            # Bu klasörlerin var olduğundan emin ol
            base_storage_dir.mkdir(parents=True, exist_ok=True)
            self.pdf_storage_dir.mkdir(parents=True, exist_ok=True)
            self.image_storage_dir.mkdir(parents=True, exist_ok=True)

            self.logger.info(f"Kalıcı PDF deposu hazır: {self.pdf_storage_dir}")
            self.logger.info(f"Kalıcı Image deposu hazır: {self.image_storage_dir}")

        except Exception as e:
            self.logger.error(f"Kalıcı depolama klasörleri oluşturulamadı: {e}")
            # Kritik hata, bu yollar olmadan devam edemeyiz
            self.pdf_storage_dir = None
            self.image_storage_dir = None

        if auto_init:
            self.initialize()

    def initialize(self) -> bool:
        """
        Database bağlantısını başlat ve tabloları oluştur

        Returns:
            bool: Başarılı ise True
        """
        try:
            self.logger.info("Database service başlatılıyor...")
            initialize_database()
            self._initialized = True
            self.logger.info("Database service hazır!")
            return True
        except Exception as e:
            self.logger.error(f"Database service başlatma hatası: {e}")
            self._initialized = False
            return False

    def is_ready(self) -> bool:
        """Database servisinin hazır olup olmadığını kontrol et"""
        return self._initialized

    # ===========================================
    # DOCUMENT & FILE OPERATIONS
    # ===========================================

    def check_existing_document(self, metadata: Dict[str, Any]) -> Optional[str]:
        """
        Metadata'ya göre mevcut belgeyi kontrol et

        Args:
            metadata: Belge metadata'sı

        Returns:
            Optional[str]: Document ID varsa, yoksa None
        """
        if not self.is_ready():
            return None

        try:
            # ✅ CRITICAL FIX: 'document_type' alanını metadata'dan çıkar
            # Bu alan sadece işlem sırasında kullanılır, database'de saklanmaz
            clean_metadata = {k: v for k, v in metadata.items() if k != 'document_type'}

            with DatabaseOperations() as db_ops:
                existing_doc = db_ops.check_duplicate_by_metadata(clean_metadata)
                if existing_doc:
                    self.logger.info(f"Mevcut belge bulundu: {existing_doc.id}")
                    return str(existing_doc.id)
                return None
        except Exception as e:
            self.logger.error(f"Duplicate kontrol hatası: {e}")
            return None

    def check_existing_file(self, file_path: str) -> Optional[Tuple[str, str]]:
        """
        Dosya hash'ine göre mevcut dosyayı kontrol et

        Args:
            file_path: Kontrol edilecek dosya yolu

        Returns:
            Optional[Tuple[str, str]]: (document_id, file_id) varsa, yoksa None
        """
        if not self.is_ready():
            return None

        try:
            with DatabaseOperations() as db_ops:
                # PDF dosyaları için kontrol et
                existing_file = db_ops.check_file_exists_by_hash(file_path, 'pdf')
                if existing_file:
                    self.logger.info(f"Mevcut dosya bulundu: {existing_file.id}")
                    return (str(existing_file.document_id), str(existing_file.id))
                return None
        except Exception as e:
            self.logger.error(f"Dosya hash kontrol hatası: {e}")
            return None

    def save_document_and_file(self,
                               metadata: Dict[str, Any],
                               file_info: Dict[str, Any]) -> Optional[str]:
        """
        Yeni belge ve dosyayı kaydet
        (GÜNCELLENDİ: Dosyayı tipine göre 'pdf' veya 'images' klasörüne kopyala)

        Args:
            metadata: Belge metadata'sı
            file_info: Dosya bilgileri (filename, file_path, file_size, etc.)
                      'file_path' burada GEÇİCİ yolu gösterir.

        Returns:
            Optional[str]: Document ID başarılı ise
        """
        if not self.is_ready():
            return None

        # Depolama yollarının düzgün yüklendiğini kontrol et
        if not self.pdf_storage_dir or not self.image_storage_dir:
            self.logger.error("❌ Kalıcı depolama yolları tanımlanmamış. İşlem iptal edildi.")
            return None

        original_temp_path_str = file_info.get('file_path')
        if not original_temp_path_str:
            self.logger.error("❌ file_info içinde 'file_path' (geçici yol) bulunamadı.")
            return None

        original_temp_path = Path(original_temp_path_str)
        if not original_temp_path.exists():
            self.logger.error(f"❌ Geçici dosya bulunamadı: {original_temp_path}")
            return None

        try:
            # ✅ CRITICAL FIX: 'document_type' alanını metadata'dan çıkar
            clean_metadata = {k: v for k, v in metadata.items() if k != 'document_type'}

            with DatabaseOperations() as db_ops:
                # 1. Önce Document'i oluştur (ID'sini almak için)
                doc_id = db_ops.create_document(clean_metadata)

                if not doc_id:
                    self.logger.error("❌ Document oluşturulamadı")
                    return None

                self.logger.info(f"✅ Document oluşturuldu: {doc_id}")

                # 2. Dosya için yeni bir kalıcı isim oluştur
                file_extension = original_temp_path.suffix
                new_filename = f"{doc_id}{file_extension}"

                # 3. ✅ YENİ: Dosya tipine göre doğru hedef klasörü seç
                file_type = file_info.get('file_type')
                target_directory: Path

                if file_type == 'pdf':
                    target_directory = self.pdf_storage_dir
                elif file_type == 'image':
                    target_directory = self.image_storage_dir
                else:
                    self.logger.error(f"❌ Desteklenmeyen dosya tipi: {file_type}. Dosya kaydedilemedi.")
                    return None

                permanent_file_path = target_directory / new_filename

                # 4. Dosyayı geçici yoldan kalıcı yola KOPYALA
                try:
                    shutil.copyfile(original_temp_path, permanent_file_path)
                    self.logger.info(f"📁 Dosya kalıcı yola kopyalandı: {permanent_file_path}")
                except Exception as copy_err:
                    self.logger.error(f"❌ Dosya kopyalama hatası: {copy_err}")
                    return None

                # 5. file_data'yı YENİ KALICI YOL ile hazırla
                file_data = {
                    'filename': new_filename,  # Yeni kalıcı ad
                    'original_filename': file_info.get('original_filename') or file_info.get('filename'),
                    'file_path': str(permanent_file_path.resolve()),  # YENİ KALICI YOL
                    'file_size': file_info.get('file_size') or permanent_file_path.stat().st_size,
                    'mime_type': file_info.get('mime_type'),
                    'file_type': file_info.get('file_type')
                }

                # 6. Dosya kaydını veritabanına ekle (bu artık kalıcı ve doğru yolu içeriyor)
                file_id = db_ops.add_file_to_document(str(doc_id), file_data)

                if not file_id:
                    self.logger.warning(f"⚠️ Dosya eklenemedi ama document oluşturuldu: {doc_id}")
                else:
                    self.logger.info(f"✅ Dosya kaydedildi - ID: {file_id}")

                self.logger.info(f"✅ Belge ve kalıcı dosya kaydedildi: {doc_id}")
                return doc_id

        except Exception as e:
            self.logger.error(f"❌ Belge kaydetme hatası: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    def _calculate_file_hash(self, file_path: str) -> Optional[str]:
        """
        Dosya hash'ini hesapla

        Args:
            file_path: Dosya yolu

        Returns:
            Optional[str]: SHA256 hash
        """
        if not file_path or not Path(file_path).exists():
            return None

        try:
            import hashlib
            sha256_hash = hashlib.sha256()

            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)

            return sha256_hash.hexdigest()
        except Exception as e:
            self.logger.error(f"Hash hesaplama hatası: {e}")
            return None

    def get_document_with_results(self, document_id: str) -> Optional[Dict[str, Any]]:
        """
        Document'i tüm sonuçlarıyla birlikte getir

        Args:
            document_id: Document ID

        Returns:
            Optional[Dict]: Document bilgileri ve sonuçları
        """
        if not self.is_ready():
            return None

        try:
            with DatabaseOperations() as db_ops:
                document = db_ops.get_document_by_id(document_id)
                if not document:
                    return None

                # OCR sonuçlarını getir
                ocr_result = db_ops.get_ocr_results_by_document(document_id)

                # Detection sonuçlarını getir
                detection_results = db_ops.get_detection_results_by_document(document_id)

                return {
                    'document': {
                        'id': str(document.id),
                        'title': document.title,
                        'metadata_type': document.metadata_type,
                        'author': document.author,
                        'created_at': document.created_at.isoformat() if document.created_at else None
                    },
                    'ocr_result': {
                        'markdown_content': ocr_result.markdown_content,
                        'xml_content': ocr_result.xml_content,
                        'total_pages': ocr_result.total_pages,
                        'confidence_score': float(ocr_result.confidence_score) if ocr_result.confidence_score else None
                    } if ocr_result else None,
                    'detection_results': [
                        {
                            'page_number': result.page_number,
                            'text_regions': result.text_regions,
                            'region_count': result.region_count,
                            'average_confidence': float(
                                result.average_confidence) if result.average_confidence else None
                        } for result in detection_results
                    ] if detection_results else []
                }

        except Exception as e:
            self.logger.error(f"Document getirme hatası: {e}")
            return None

    # ===========================================
    # PROCESSING JOB OPERATIONS
    # ===========================================

    def create_processing_job(self,
                              document_id: str,
                              process_mode: str,
                              output_formats: List[str]) -> Optional[str]:
        """
        Yeni processing job oluştur

        Args:
            document_id: Document ID
            process_mode: 'ocr' veya 'detection'
            output_formats: ['md', 'xml'] listesi

        Returns:
            Optional[str]: Job ID başarılı ise
        """
        if not self.is_ready():
            return None

        try:
            with DatabaseOperations() as db_ops:
                job_id = db_ops.create_processing_job(document_id, process_mode, output_formats)
                if job_id:
                    self.logger.info(f"Processing job oluşturuldu: {job_id}")
                return job_id
        except Exception as e:
            self.logger.error(f"Processing job oluşturma hatası: {e}")
            return None

    def update_job_progress(self,
                            job_id: str,
                            progress: int,
                            current_page: int = None,
                            total_pages: int = None) -> bool:
        """
        Job progress'ini güncelle

        Args:
            job_id: Job ID
            progress: Progress yüzdesi (0-100)
            current_page: Mevcut sayfa
            total_pages: Toplam sayfa

        Returns:
            bool: Başarılı ise True
        """
        if not self.is_ready():
            return False

        try:
            with DatabaseOperations() as db_ops:
                update_data = {
                    'progress_percent': progress
                }
                if current_page is not None:
                    update_data['current_page'] = current_page
                if total_pages is not None:
                    update_data['total_pages'] = total_pages

                return db_ops.update_job_status(job_id, 'processing', **update_data)
        except Exception as e:
            self.logger.error(f"Job progress güncelleme hatası: {e}")
            return False

    def complete_job(self, job_id: str, success: bool = True) -> bool:
        """
        Job'ı tamamla

        Args:
            job_id: Job ID
            success: Başarılı mı

        Returns:
            bool: Güncelleme başarılı ise True
        """
        if not self.is_ready():
            return False

        try:
            with DatabaseOperations() as db_ops:
                status = 'completed' if success else 'failed'
                return db_ops.update_job_status(job_id, status)
        except Exception as e:
            self.logger.error(f"Job tamamlama hatası: {e}")
            return False

    # ===========================================
    # RESULTS OPERATIONS
    # ===========================================

    def save_ocr_results(self,
                         job_id: str,
                         document_id: str,
                         ocr_data: Dict[str, Any]) -> bool:
        """
        OCR sonuçlarını kaydet

        Args:
            job_id: Job ID
            document_id: Document ID
            ocr_data: OCR sonuç verisi (outputs içindeki md/xml content'ler)

        Returns:
            bool: Başarılı ise True
        """
        if not self.is_ready():
            return False

        try:
            # OCR data'yı database formatına çevir
            result_data = {
                'markdown_content': ocr_data.get('outputs', {}).get('md', ''),
                'xml_content': ocr_data.get('outputs', {}).get('xml', ''),
                'total_pages': ocr_data.get('page_count', 0),
                'processing_time_seconds': ocr_data.get('processing_time', 0)
            }

            # Confidence ve karakter sayısı hesapla
            if 'ocr_results' in ocr_data:
                total_chars = 0
                total_confidence = 0.0
                confidence_count = 0

                for page in ocr_data['ocr_results']:
                    for paragraph in page.get('paragraphs', []):
                        text = paragraph.get('text', '')
                        conf = paragraph.get('confidence', 0.0)

                        total_chars += len(text)
                        if conf > 0:
                            total_confidence += conf
                            confidence_count += 1

                result_data['total_characters'] = total_chars
                if confidence_count > 0:
                    result_data['confidence_score'] = total_confidence / confidence_count

                    # Characters per second hesapla
                    processing_time = result_data['processing_time_seconds']
                    if processing_time > 0:
                        result_data['characters_per_second'] = total_chars / processing_time

            with DatabaseOperations() as db_ops:
                result_id = db_ops.save_ocr_results(job_id, document_id, result_data)
                if result_id:
                    self.logger.info(f"OCR sonuçları kaydedildi: {result_id}")
                    return True
                return False

        except Exception as e:
            self.logger.error(f"OCR sonuç kaydetme hatası: {e}")
            return False

    def save_detection_results(self,
                               job_id: str,
                               document_id: str,
                               detection_data: List[Dict[str, Any]]) -> bool:
        """
        Detection sonuçlarını kaydet

        Args:
            job_id: Job ID
            document_id: Document ID
            detection_data: Detection sonuç listesi

        Returns:
            bool: Başarılı ise True
        """
        if not self.is_ready():
            return False

        try:
            # Detection data'yı database formatına çevir
            page_results = []

            for page_data in detection_data:
                page_result = {
                    'page_number': page_data['page_number'],
                    'total_pages': len(detection_data),
                    'text_regions': page_data['text_regions'],
                    'region_count': page_data.get('region_count', len(page_data.get('text_regions', []))),
                }

                # Average confidence hesapla
                regions = page_data.get('text_regions', [])
                if regions:
                    total_conf = sum(region.get('confidence', 0.0) for region in regions)
                    page_result['average_confidence'] = total_conf / len(regions)

                page_results.append(page_result)

            with DatabaseOperations() as db_ops:
                success = db_ops.save_detection_results(job_id, document_id, page_results)
                if success:
                    self.logger.info(f"Detection sonuçları kaydedildi: {len(page_results)} sayfa")
                return success

        except Exception as e:
            self.logger.error(f"Detection sonuç kaydetme hatası: {e}")
            return False

    # ===========================================
    # UTILITY & STATS OPERATIONS
    # ===========================================

    def get_system_stats(self) -> Dict[str, Any]:
        """
        Sistem istatistiklerini getir

        Returns:
            Dict: Sistem istatistikleri
        """
        if not self.is_ready():
            return {}

        try:
            with DatabaseOperations() as db_ops:
                stats = db_ops.get_database_stats()

                # Günlük stats'ı da güncelle
                db_ops.update_daily_stats()

                return stats
        except Exception as e:
            self.logger.error(f"Sistem istatistikleri hatası: {e}")
            return {}

    def prepare_file_info(self, file_path: str, original_filename: str = None) -> Dict[str, Any]:
        """
        Dosya bilgilerini database için hazırla - HASH EKLENDİ

        Args:
            file_path: Dosya yolu
            original_filename: Orijinal dosya adı

        Returns:
            Dict: Database için hazır dosya bilgileri
        """
        try:
            p = Path(file_path)

            if not p.exists():
                raise FileNotFoundError(f"Dosya bulunamadı: {file_path}")

            # MIME type belirleme
            ext = p.suffix.lower()
            mime_types = {
                '.pdf': 'application/pdf',
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.tif': 'image/tiff',
                '.tiff': 'image/tiff',
                '.bmp': 'image/bmp',
                '.webp': 'image/webp'
            }

            file_type = 'pdf' if ext == '.pdf' else 'image'

            # ✅ Hash hesapla
            file_hash = self._calculate_file_hash(str(p.absolute()))

            return {
                'filename': p.name,
                'file_name': p.name,  # Her iki key de ekle (uyumluluk için)
                'original_filename': original_filename or p.name,
                'file_path': str(p.absolute()),  # ✅ ABSOLUTE PATH
                'file_size': p.stat().st_size,
                'mime_type': mime_types.get(ext, 'application/octet-stream'),
                'file_type': file_type,
                'file_hash': file_hash  # ✅ HASH EKLENDİ
            }

        except Exception as e:
            self.logger.error(f"Dosya bilgisi hazırlama hatası: {e}")
            return {}

    def log_processing_start(self, filename: str, process_mode: str) -> None:
        """İşlem başlangıcını logla"""
        self.logger.info(f"İşlem başlatıldı: {filename} ({process_mode})")

    def log_processing_complete(self, filename: str, success: bool, duration: float) -> None:
        """İşlem tamamlanmasını logla"""
        status = "başarılı" if success else "başarısız"
        self.logger.info(f"İşlem tamamlandı: {filename} - {status} ({duration:.2f}s)")

    def cleanup_old_data(self, days_old: int = 7) -> bool:
        """
        Eski verileri temizle

        Args:
            days_old: Kaç gün önceki veriler temizlensin

        Returns:
            bool: Başarılı ise True
        """
        if not self.is_ready():
            return False

        try:
            with DatabaseOperations() as db_ops:
                return db_ops.cleanup_old_data(days_old)
        except Exception as e:
            self.logger.error(f"Veri temizleme hatası: {e}")
            return False


# Global instance - Backend tarafından kullanılacak
db_service = None


def get_database_service(auto_init: bool = True) -> DatabaseService:
    """
    Global database service instance'ını getir

    Args:
        auto_init: İlk çağrıda otomatik initialize et

    Returns:
        DatabaseService: Service instance
    """
    global db_service

    if db_service is None:
        db_service = DatabaseService(auto_init=auto_init)

    return db_service


def initialize_database_service() -> bool:
    """
    Database service'i backend başlangıcında initialize et

    Returns:
        bool: Başarılı ise True
    """
    try:
        service = get_database_service()
        return service.is_ready()
    except Exception as e:
        print(f"Database service initialization error: {e}")
        return False


# Convenience functions for quick operations
def check_document_exists(metadata: Dict[str, Any]) -> Optional[str]:
    """Belge var mı kontrol et"""
    return get_database_service().check_existing_document(metadata)


def check_file_exists(file_path: str) -> Optional[Tuple[str, str]]:
    """Dosya var mı kontrol et"""
    return get_database_service().check_existing_file(file_path)


def save_processing_results(document_id: str,
                            job_id: str,
                            result_data: Dict[str, Any]) -> bool:
    """İşlem sonuçlarını kaydet"""
    service = get_database_service()

    if result_data.get('process_mode') == 'ocr':
        return service.save_ocr_results(job_id, document_id, result_data)
    elif result_data.get('process_mode') == 'detection':
        detection_results = result_data.get('detection_results', [])
        return service.save_detection_results(job_id, document_id, detection_results)

    return False