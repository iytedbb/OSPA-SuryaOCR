"""
Backend Database Integration Module
SuryaOCR_backend.py ile database_service.py arasındaki köprü
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import logging
# Database modülü için path ekle
backend_dir = Path(__file__).parent.resolve()
# app/modules/ocr -> app/modules -> app -> app/database
project_root = backend_dir.parent.parent.parent 
database_dir = project_root / "app" / "database"

# Add app/database to sys.path if not already there
if str(database_dir) not in sys.path and database_dir.exists():
    sys.path.insert(0, str(database_dir))

# Database service'i import et
try:
    from database_service import (
        get_database_service,
        initialize_database_service,
        check_document_exists,
        check_file_exists,
        save_processing_results
    )

    DATABASE_AVAILABLE = True
    print("✅ Database service başarıyla import edildi")

except ImportError as e:
    DATABASE_AVAILABLE = False
    print(f"⚠️ Database service import edilemedi: {e}")
    print("Database özellikleri devre dışı")


class ProcessingIntegrator:
    """
    Backend ile Database arasındaki entegrasyon logic'i
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.db_enabled = DATABASE_AVAILABLE

        if self.db_enabled:
            self.db_service = get_database_service()
        else:
            self.db_service = None

    def is_database_enabled(self) -> bool:
        """Database entegrasyonu aktif mi?"""
        return self.db_enabled and self.db_service and self.db_service.is_ready()

    def check_existing_processing(self,
                                  file_path: str,
                                  metadata: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """
        Mevcut işlenmiş belge/dosya var mı kontrol et

        Args:
            file_path: Dosya yolu
            metadata: Belge metadata'sı (varsa)

        Returns:
            Optional[Dict]: Mevcut sonuçlar varsa, yoksa None
        """
        if not self.is_database_enabled():
            return None

        try:
            # 1. Önce dosya hash'ine göre kontrol et
            # DİKKAT: Eğer metadata doluysa, hash kontrolünü atlıyoruz.
            # Çünkü kullanıcı aynı dosya için farklı metadata girmiş olabilir (Yazar, Başlık değişimi vb.)
            # Bu durumda eski kaydı (eski metadata'lı) getirmek istemeyiz.
            file_result = None
            if not metadata:
                file_result = check_file_exists(file_path)
            
            if file_result:
                document_id, file_id = file_result
                self.logger.info(f"Mevcut dosya bulundu (Hash): {document_id}")

                # Document'in tüm sonuçlarını getir
                document_data = self.db_service.get_document_with_results(document_id)
                if document_data and document_data.get('ocr_result'):
                    # OCR sonuçları varsa döndür
                    return self._format_existing_results(document_data, 'ocr')
                elif document_data and document_data.get('detection_results'):
                    # Detection sonuçları varsa döndür
                    return self._format_existing_results(document_data, 'detection')

            # 2. Metadata varsa, o ile kontrol et
            if metadata:
                doc_id = check_document_exists(metadata)
                if doc_id:
                    self.logger.info(f"Metadata ile mevcut belge bulundu: {doc_id}")
                    document_data = self.db_service.get_document_with_results(doc_id)
                    if document_data:
                        if document_data.get('ocr_result'):
                            return self._format_existing_results(document_data, 'ocr')
                        elif document_data.get('detection_results'):
                            return self._format_existing_results(document_data, 'detection')

            return None

        except Exception as e:
            self.logger.error(f"Mevcut işlem kontrolü hatası: {e}")
            return None

    def _format_existing_results(self, document_data: Dict[str, Any], result_type: str) -> Dict[str, Any]:
        """
        Database'den gelen sonuçları backend formatına çevir
        """
        try:
            result = {
                'success': True,
                'from_database': True,
                'document_id': document_data['document']['id'],
                'filename': 'cached_result',
                'process_mode': result_type
            }

            if result_type == 'ocr' and document_data.get('ocr_result'):
                ocr_data = document_data['ocr_result']
                result.update({
                    'page_count': ocr_data['total_pages'],
                    'outputs': {
                        'md': ocr_data['markdown_content'] or '',
                        'xml': ocr_data['xml_content'] or ''
                    },
                    'processing_time': 0.1,  # Cache'den geldiği için çok hızlı
                    'confidence_score': ocr_data['confidence_score']
                })

                # OCR results formatına da çevir (UI için)
                result['ocr_results'] = [{
                    'page_number': 1,
                    'paragraphs': [
                        {
                            'paragraph_number': 1,
                            'text': ocr_data['markdown_content'][:500] + '...' if len(
                                ocr_data['markdown_content']) > 500 else ocr_data['markdown_content'],
                            'type': 'paragraph',
                            'confidence': ocr_data['confidence_score'] or 0.95
                        }
                    ],
                    'full_text': ocr_data['markdown_content'] or ''
                }]

            elif result_type == 'detection' and document_data.get('detection_results'):
                result.update({
                    'detection_results': document_data['detection_results']
                })

            return result

        except Exception as e:
            self.logger.error(f"Sonuç formatı dönüştürme hatası: {e}")
            return None

    def start_processing_job(self,
                             file_path: str,
                             process_mode: str,
                             output_formats: list,
                             metadata: Dict[str, Any] = None) -> Optional[Tuple[str, str]]:
        """
        Yeni işlem başlat ve database'e kaydet - DYNAMIC METADATA + FILE PATH FIX

        Args:
            file_path: Dosya yolu
            process_mode: 'ocr' veya 'detection'
            output_formats: Çıktı formatları listesi
            metadata: Belge metadata'sı (form'dan gelen) - TÜM ALANLARI DESTEKLER

        Returns:
            Optional[Tuple[str, str]]: (document_id, job_id) başarılı ise
        """
        if not self.is_database_enabled():
            return None

        try:
            # ✅ KRİTİK FIX: Dosya bilgilerini hazırla ve file_path'i sakla
            file_info = self.db_service.prepare_file_info(file_path)
            if not file_info:
                self.logger.error(f"❌ Dosya bilgileri hazırlanamadı: {file_path}")
                return None

            # ✅ ÇÖZÜM: file_path'i file_info'ya ekle (eğer yoksa)
            if 'file_path' not in file_info:
                file_info['file_path'] = str(Path(file_path).resolve())
                self.logger.info(f"✅ file_path eklendi: {file_info['file_path']}")

            # Enhanced dynamic metadata preparation
            filename = os.path.basename(file_path)
            final_metadata = self._prepare_dynamic_metadata(metadata, filename)

            # Metadata debug log
            self.debug_metadata_flow(final_metadata, "Final prepared metadata")

            # ✅ Document ve dosyayı kaydet - file_info içinde file_path var
            document_id = self.db_service.save_document_and_file(final_metadata, file_info)
            if not document_id:
                self.logger.error("Document kaydedilemedi")
                return None

            self.logger.info(f"✅ Document kaydedildi: {document_id}")
            self.logger.info(f"✅ Dosya yolu: {file_info.get('file_path')}")

            # Processing job oluştur
            job_id = self.db_service.create_processing_job(document_id, process_mode, output_formats)
            if not job_id:
                self.logger.error("Processing job oluşturulamadı")
                return None

            self.logger.info(f"İşlem kaydı oluşturuldu - Doc: {document_id}, Job: {job_id}")
            self.logger.info(f"Dynamic metadata başarıyla dahil edildi: {final_metadata.get('title', 'N/A')}")
            return (document_id, job_id)

        except Exception as e:
            self.logger.error(f"İşlem başlatma kayıt hatası: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    def _prepare_dynamic_metadata(self, user_metadata: Dict[str, Any], filename: str) -> Dict[str, Any]:
        """
        Frontend'ten gelen metadata'yı dinamik olarak işler ve database'e uygun hale getirir.
        Hem modern Türkçe tarihleri hem Osmanlıca tarihleri hem de 01/01/1895 gibi formatları destekler.
        Gazete tipi için newspaper_name alanını otomatik doldurur ve publication alanını temizler.
        """
        from datetime import datetime
        import re
        import locale

        # Osmanlıca → Modern ay isimleri eşleme tablosu
        osmanlica_aylar = {
            "kanunusani": "ocak",
            "şubat": "şubat",
            "mart": "mart",
            "nisan": "nisan",
            "mayıs": "mayıs",
            "haziran": "haziran",
            "temmuz": "temmuz",
            "ağustos": "ağustos",
            "eylül": "eylül",
            "teşrinievvel": "ekim",
            "teşrinisani": "kasım",
            "kanunuevvel": "aralık",
        }

        # Türkçe locale ayarla (Linux ve Windows uyumu)
        try:
            locale.setlocale(locale.LC_TIME, 'tr_TR.UTF-8')
        except locale.Error:
            try:
                locale.setlocale(locale.LC_TIME, 'Turkish_Turkey.1254')
            except locale.Error:
                self.logger.warning("⚠️ Türkçe locale ayarlanamadı, tarih parse işlemi sınırlı olabilir.")

        if not user_metadata or not isinstance(user_metadata, dict):
            self.logger.info(f"Minimal metadata oluşturuluyor: {filename}")
            return {
                'title': filename,
                'metadata_type': 'article',
                'language': 'tr',
                'citation_style': 'apa'
            }

        final_metadata = {}

        # Frontend'ten gelen tüm alanları doğrudan taşı
        for key, value in user_metadata.items():
            if value is not None:
                # Değer string ise temizle, değilse olduğu gibi al
                if isinstance(value, str):
                    clean_val = value.strip()
                    if clean_val:
                        final_metadata[key] = clean_val
                else:
                    final_metadata[key] = value

        # ✅ TİP DÖNÜŞÜMLERİ (DB modelindeki integer alanlar için)
        int_fields = ['publication_year', 'page_count', 'pages'] # 'pages' bazen string bazen int olabiliyor modelde string(50)
        for field in int_fields:
            if field in final_metadata and final_metadata[field]:
                try:
                    # 'pages' alanı modelde String(50), o yüzden onu int yapmıyoruz 
                    # ama publication_year ve page_count kesin int.
                    if field != 'pages':
                        final_metadata[field] = int(str(final_metadata[field]).strip())
                except (ValueError, TypeError):
                    self.logger.warning(f"Field {field} could not be converted to int: {final_metadata[field]}")

        # ✅ ZORUNLU ALAN KONTROLÜ (Başlık ve Tür)
        if 'title' not in final_metadata or not final_metadata['title']:
            final_metadata['title'] = filename
            self.logger.info(f"Başlık eksik, dosya adı kullanılıyor: {filename}")

        if 'metadata_type' not in final_metadata:
            final_metadata['metadata_type'] = 'article'

        # ✅ PAGES ALANI İÇİN ÖZEL İŞLEME
        if 'pages' in final_metadata:
            pages_value = final_metadata['pages']

            # Eğer "1-8" gibi range ise, sadece ilk sayıyı al veya page_range'e taşı
            if '-' in pages_value or '–' in pages_value:
                # page_range alanına taşı (eğer varsa)
                final_metadata['page_range'] = pages_value

                # pages alanını ilk sayfa veya toplam sayfa sayısı yap
                try:
                    # "1-8" -> 8 sayfa
                    parts = re.split(r'[-–]', pages_value)
                    if len(parts) == 2:
                        start = int(parts[0].strip())
                        end = int(parts[1].strip())
                        page_count = end - start + 1
                        final_metadata['pages'] = str(page_count)
                        self.logger.info(f"Sayfa aralığı dönüştürüldü: '{pages_value}' -> {page_count} sayfa")
                    else:
                        # Parse edilemezse kaldır
                        del final_metadata['pages']
                        self.logger.warning(f"Sayfa aralığı parse edilemedi, kaldırıldı: {pages_value}")
                except (ValueError, IndexError):
                    # Parse hatası - pages'i kaldır
                    del final_metadata['pages']
                    self.logger.warning(f"Sayfa değeri geçersiz, kaldırıldı: {pages_value}")
            else:
                # Normal integer değer - doğrula
                try:
                    int(pages_value)  # Validasyon
                except ValueError:
                    # Integer değilse kaldır
                    del final_metadata['pages']
                    self.logger.warning(f"Sayfa değeri integer değil, kaldırıldı: {pages_value}")

        # 📅 --- TARİH ALANI FORMATLAMA ---
        def parse_tarih(raw_date: str) -> Optional[str]:
            if not raw_date:
                return None
            raw_date = raw_date.strip().lower()

            # 1️⃣ Numeric formatlar (01/01/1895 veya 01.01.1895 veya 1895-01-01)
            numeric_patterns = [
                ("%d/%m/%Y", r"\d{1,2}/\d{1,2}/\d{4}"),
                ("%d.%m.%Y", r"\d{1,2}\.\d{1,2}\.\d{4}"),
                ("%Y-%m-%d", r"\d{4}-\d{1,2}-\d{1,2}")
            ]
            for fmt, pattern in numeric_patterns:
                if re.fullmatch(pattern, raw_date):
                    try:
                        parsed = datetime.strptime(raw_date, fmt)
                        return parsed.strftime("%Y-%m-%d")
                    except Exception:
                        pass

            # 2️⃣ Modern Türkçe tarih formatı: "4 Ekim 1932"
            try:
                parsed = datetime.strptime(raw_date, "%d %B %Y")
                return parsed.strftime("%Y-%m-%d")
            except Exception:
                pass

            # 3️⃣ Osmanlıca ay isimleri içeren formatlar
            # Örnek: "4 Kanunusani 1321" veya "Kanunusani 4 1321"
            for os_ay, modern_ay in osmanlica_aylar.items():
                if os_ay in raw_date:
                    # Ay ismini modern Türkçe ay ile değiştir
                    modern_date = raw_date.replace(os_ay, modern_ay)
                    # Geriye kalan kısım "4 ocak 1321" gibi olur
                    # Rakamlar hicri olabilir ama yine de parse etmeyi deneyelim
                    match = re.search(r"(\d{1,2})\s+([a-zçğıöşü]+)\s+(\d{3,4})", modern_date)
                    if match:
                        day, month, year = match.groups()
                        try:
                            parsed = datetime.strptime(f"{day} {month} {year}", "%d %B %Y")
                            return parsed.strftime("%Y-%m-%d")
                        except Exception:
                            # Eğer datetime kabul etmezse elle birleştir (örnek: hicri 1321)
                            return f"{year}-01-01"
            return None

        if 'date' in final_metadata:
            formatted_date = parse_tarih(final_metadata['date'])
            if formatted_date:
                self.logger.info(f"Tarih formatlandı: {final_metadata['date']} -> {formatted_date}")
                final_metadata['date'] = formatted_date
            else:
                self.logger.warning(
                    f"Tarih parse edilemedi, DB hatası önlenmesi için 'date' alanı kaldırıldı: {final_metadata['date']}")
                del final_metadata['date']

        # 📝 Zorunlu alanların fallback'leri
        metadata_type = user_metadata.get('metadata_type', '').strip().lower() if user_metadata else ''
        if metadata_type not in ['book', 'article', 'encyclopedia', 'newspaper']:
            metadata_type = 'article'

        required_defaults = {
            'title': filename,
            'metadata_type': metadata_type,
            'language': 'tr',
            'citation_style': 'apa'
        }

        for field, default_value in required_defaults.items():
            if not final_metadata.get(field):
                final_metadata[field] = default_value
                self.logger.info(f"Default değer atandı: {field} = {default_value}")

        # 🧹 Sistemsel ve işlemle ilgili alanları temizle (DB modelinde olmayanlar)
        system_fields = [
            'processed_by', 'processing_date', 'ocr_confidence', 
            'source_filename', 'source_format', 'document_type',
            'file_path', 'process_mode', 'output_formats', 
            'original_filename_for_stream', 'progress_key'
        ]
        for field in system_fields:
            if field in final_metadata:
                del final_metadata[field]

        # 🗞️ Gazete tipi için özel kurallar
        if final_metadata.get('metadata_type') == 'newspaper':
            # newspaper_name otomatik doldurma
            if not final_metadata.get('newspaper_name'):
                publication_name = final_metadata.get('publication')
                if publication_name:
                    final_metadata['newspaper_name'] = publication_name
                    self.logger.info(f"'newspaper_name' alanı otomatik dolduruldu: {publication_name}")
                else:
                    self.logger.warning("⚠️ newspaper_name alanı eksik ve publication da yok. Bu DB constraint hatasına yol açabilir.")

            # publication alanını temizle (DB constraint gereği)
            if 'publication' in final_metadata:
                self.logger.info("Gazete türü için 'publication' alanı kaldırıldı (DB uyumu)")
                del final_metadata['publication']

        # Loglama
        self.logger.info(f"Dynamic metadata işlendi - {len(final_metadata)} alan:")
        for key, value in final_metadata.items():
            if len(str(value)) > 50:
                display_value = str(value)[:47] + "..."
            else:
                display_value = str(value)
            self.logger.info(f"  {key}: {display_value}")

        return final_metadata


    def update_processing_progress(self,
                                   job_id: str,
                                   progress: int,
                                   current_page: int = None,
                                   total_pages: int = None) -> bool:
        """
        İşlem progress'ini database'de güncelle
        """
        if not self.is_database_enabled() or not job_id:
            return False

        try:
            return self.db_service.update_job_progress(job_id, progress, current_page, total_pages)
        except Exception as e:
            self.logger.error(f"Progress güncelleme hatası: {e}")
            return False

    def finish_processing_job(self,
                              document_id: str,
                              job_id: str,
                              result_data: Dict[str, Any]) -> bool:
        """
        İşlem sonuçlarını database'e kaydet ve job'ı tamamla

        Args:
            document_id: Document ID
            job_id: Job ID
            result_data: Backend'den gelen sonuç data'sı

        Returns:
            bool: Başarılı ise True
        """
        if not self.is_database_enabled():
            return False

        try:
            success = result_data.get('success', False)

            if success:
                # Sonuçları kaydet
                save_success = save_processing_results(document_id, job_id, result_data)
                if save_success:
                    self.logger.info(f"Sonuçlar kaydedildi - Doc: {document_id}, Job: {job_id}")

                # Job'ı complete olarak işaretle
                self.db_service.complete_job(job_id, success=True)
                return save_success
            else:
                # Hata durumunda job'ı failed olarak işaretle
                self.db_service.complete_job(job_id, success=False)
                return False

        except Exception as e:
            self.logger.error(f"İşlem sonuçlandırma hatası: {e}")
            # Hata durumunda job'ı failed olarak işaretle
            try:
                self.db_service.complete_job(job_id, success=False)
            except:
                pass
            return False

    def get_processing_statistics(self) -> Dict[str, Any]:
        """
        İşlem istatistiklerini getir

        Returns:
            Dict: Sistem istatistikleri
        """
        if not self.is_database_enabled():
            return {
                'database_enabled': False,
                'total_documents': 0,
                'total_jobs': 0,
                'completed_jobs': 0
            }

        try:
            stats = self.db_service.get_system_stats()
            stats['database_enabled'] = True
            return stats
        except Exception as e:
            self.logger.error(f"İstatistik getirme hatası: {e}")
            return {'database_enabled': True, 'error': str(e)}

    def debug_metadata_flow(self, metadata: Dict[str, Any], context: str = ""):
        """
        Debug helper to track metadata flow through the system
        """
        self.logger.info(f"=== METADATA DEBUG - {context} ===")
        if not metadata:
            self.logger.info("No metadata provided")
            return

        self.logger.info(f"Metadata keys: {list(metadata.keys())}")
        self.logger.info(f"Metadata type: {type(metadata)}")

        # Log important fields
        important_fields = ['title', 'author', 'metadata_type', 'language', 'citation_style', 'doi']
        for field in important_fields:
            value = metadata.get(field)
            if value:
                self.logger.info(f"  {field}: '{value}'")
            else:
                self.logger.info(f"  {field}: [empty/missing]")

        # Log additional fields (dynamic support)
        additional_fields = ['publisher', 'publication_year', 'publication_city', 'edition', 'volume', 'pages']
        for field in additional_fields:
            value = metadata.get(field)
            if value:
                self.logger.info(f"  {field}: '{value}'")

        self.logger.info(f"=== END METADATA DEBUG - {context} ===")


# Global integrator instance
_processing_integrator = None


def get_processing_integrator() -> ProcessingIntegrator:
    """
    Global processing integrator instance'ını getir

    Returns:
        ProcessingIntegrator: Integrator instance
    """
    global _processing_integrator

    if _processing_integrator is None:
        _processing_integrator = ProcessingIntegrator()

    return _processing_integrator


def initialize_processing_integration() -> bool:
    """
    Processing integration'ı backend başlangıcında initialize et

    Returns:
        bool: Başarılı ise True
    """
    try:
        if not DATABASE_AVAILABLE:
            print("Database entegrasyonu kullanılamıyor")
            return False

        # Database service'i initialize et
        db_initialized = initialize_database_service()
        if db_initialized:
            print("Database entegrasyonu hazır")
        else:
            print("Database entegrasyonu başlatılamadı")

        # Integrator'ı oluştur (database olmasa da çalışır)
        integrator = get_processing_integrator()

        return True

    except Exception as e:
        print(f"Processing integration initialization error: {e}")
        return False


# Convenience wrapper functions for backend
def check_for_existing_results(file_path: str, metadata: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
    """
    Mevcut sonuçları kontrol et - Backend'in kullanacağı function

    Args:
        file_path: Dosya yolu
        metadata: Belge metadata'sı

    Returns:
        Optional[Dict]: Mevcut sonuçlar varsa
    """
    integrator = get_processing_integrator()
    return integrator.check_existing_processing(file_path, metadata)


def register_new_processing(file_path: str,
                            process_mode: str,
                            output_formats: list,
                            metadata: Dict[str, Any] = None) -> Optional[Tuple[str, str]]:
    """
    Yeni işlemi database'e kaydet - Backend'in kullanacağı function - DYNAMIC METADATA

    Args:
        file_path: Dosya yolu
        process_mode: İşlem modu
        output_formats: Çıktı formatları
        metadata: Frontend'ten gelen TÜM metadata alanları

    Returns:
        Optional[Tuple[str, str]]: (document_id, job_id) tuple'ı
    """
    integrator = get_processing_integrator()
    return integrator.start_processing_job(file_path, process_mode, output_formats, metadata)


def update_job_progress(job_id: str, progress: int, current_page: int = None, total_pages: int = None) -> bool:
    """
    Job progress'ini güncelle - Backend'in kullanacağı function
    """
    integrator = get_processing_integrator()
    return integrator.update_processing_progress(job_id, progress, current_page, total_pages)


def finalize_processing(document_id: str, job_id: str, result_data: Dict[str, Any]) -> bool:
    """
    İşlem sonuçlarını finalize et - Backend'in kullanacağı function
    """
    integrator = get_processing_integrator()
    return integrator.finish_processing_job(document_id, job_id, result_data)


def get_system_statistics() -> Dict[str, Any]:
    """
    Sistem istatistiklerini getir - Backend'in kullanacağı function
    """
    integrator = get_processing_integrator()
    return integrator.get_processing_statistics()


def is_database_integration_enabled() -> bool:
    """
    Database entegrasyonu aktif mi kontrol et
    """
    integrator = get_processing_integrator()
    return integrator.is_database_enabled()