# Thanks to https://github.com/datalab-to/surya
import os
import json
import queue
import traceback
import io
import base64
from PIL import Image, ImageDraw, ImageFont

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Any
import tempfile
import time
from datetime import datetime
from io import BytesIO
import torch
import re
import threading
import fitz  # PyMuPDF

# Flask imports
from flask import request, jsonify, send_file, Response, stream_with_context, Blueprint, current_app
from flask import request, jsonify, send_file, Response, stream_with_context, Blueprint, current_app
from flask_cors import CORS
import zipfile

from .DocumentMetadata import DocumentMetadata, MetadataManager, create_metadata_from_form, get_metadata_schema
# from .GazeteOCRProcessor import GazeteOCRProcessor # Circular import risk, importing inside class or later might be safer but let's try module level first if no circular dependency
# GazeteOCRProcessor is imported later inside a method in original code too?
# Line 26 was: from GazeteOCRProcessor import GazeteOCRProcessor

# SuryaOCR imports - Gerçek API yapısı (GitHub: datalab-to/surya)
SURYA_AVAILABLE = False
SURYA_API = None  # "new" | "old"

# Use the blueprint from __init__
from . import api_bp

try:
    # Import both the blueprint AND the job_results dictionary
    from .on_isleme_main import preprocess_bp, job_results as preprocessing_job_results

    PREPROCESSING_AVAILABLE = True
    print("✅ Ön işleme Blueprint ve job_results başarıyla import edildi.")
except ImportError as e:
    print(f"⚠️ Ön işleme modülü import edilemedi: {e}")
    print("   'on_isleme_main.py' dosyasının 'SuryaOCR_backend.py' ile aynı dizinde olduğundan emin olun.")
    preprocess_bp = None
    # Define job_results here if import fails to avoid NameError later
    preprocessing_job_results = {}  # Ensure this is defined even on import error
    PREPROCESSING_AVAILABLE = False

try:
    # API (Predictor sınıfları)
    from surya.recognition import RecognitionPredictor
    from surya.detection import DetectionPredictor

    try:
        from surya.recognition.languages import CODE_TO_LANGUAGE
    except Exception:
        CODE_TO_LANGUAGE = None  # diller opsiyonel

    SURYA_AVAILABLE = True
    SURYA_API = "new"
    print("✅ SuryaOCR (new API) import OK")
except ImportError as e_new:
    print(f"⚠️ Yeni API import olmadı: {e_new}")
    try:
        # 🕰️ Eski API (run_ocr, batch_text_detection)
        from surya.ocr import run_ocr
        from surya.detection import batch_text_detection

        CODE_TO_LANGUAGE = None
        SURYA_AVAILABLE = True
        SURYA_API = "old"
        print("✅ SuryaOCR (old API) import OK")
    except ImportError as e_old:
        print(f"❌ SuryaOCR import hatası: {e_old}")
        print("Lütfen bu ortamda 'pip install --upgrade surya-ocr' deneyin")

try:
    from .database_integration import (
        initialize_processing_integration,
        is_database_integration_enabled,
        check_for_existing_results,
        register_new_processing,
        update_job_progress,
        finalize_processing,
        get_system_statistics
    )

    DATABASE_INTEGRATION_AVAILABLE = True
    print("✅ Database entegrasyonu yüklendi")
except ImportError as e:
    DATABASE_INTEGRATION_AVAILABLE = False
    print(f"⚠️ Database entegrasyonu yüklenemedi: {e}")

try:
    # Add layout analysis import alongside existing imports
    from surya.layout import LayoutPredictor

    LAYOUT_AVAILABLE = True
    print("✅ LayoutPredictor import OK")
except ImportError as e:
    LAYOUT_AVAILABLE = False
    print(f"⚠️ LayoutPredictor import failed: {e}")


def format_duration(seconds: float) -> str:
    """Verilen saniye değerini saat/dakika/saniye formatına çevirir."""
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"{hours} saat {minutes} dk {secs} sn"
    elif minutes > 0:
        return f"{minutes} dk {secs} sn"
    else:
        return f"{secs} sn"


class SuryaProcessor:
    """SuryaOCR işlem sınıfı - Gerçek GitHub API ile"""
    current_document_id = None
    current_job_id = None

    def __init__(self):
        """Processor'ı başlat ve modelleri yükle"""
        if not SURYA_AVAILABLE:
            raise Exception("SuryaOCR kütüphanesi bulunamadı")

        print("🚀 SuryaOCR Processor başlatılıyor...")

        # GPU kontrolü
        self._setup_gpu_optimization()

        # Modelleri yükle
        self._load_models()

        # Metadata manager'ı başlat
        self.metadata_manager = MetadataManager()

        self.layout_lock = threading.Lock()
        print("🔒 Layout model lock oluşturuldu")

        # Gazete processor ekle
        self.gazete_processor = None
        self._init_gazete_processor()

        print("✅ SuryaOCR Processor hazır!")

    def _init_gazete_processor(self):
        """Gazete işleme modülünü başlat - UPDATED: Surya Layout desteği"""
        try:
            from .GazeteOCRProcessor import GazeteOCRProcessor

            # YOLO model path'i bul (birden fazla olası konum)
            backend_dir = Path(__file__).parent

            possible_paths = [
                backend_dir / "database" / "models" / "doclayout_yolo_docstructbench_imgsz1024.pt",
                backend_dir / ".." / "database" / "models" / "doclayout_yolo_docstructbench_imgsz1024.pt",
                # ← ÖNEMLİ EKLEME
                backend_dir / "models" / "doclayout_yolo_docstructbench_imgsz1024.pt",
                backend_dir.parent / "models" / "doclayout_yolo_docstructbench_imgsz1024.pt",
                backend_dir.parent.parent / "models" / "doclayout_yolo_docstructbench_imgsz1024.pt",
                # ← GitHub root için
                backend_dir.parent.parent / "database" / "models" / "doclayout_yolo_docstructbench_imgsz1024.pt", # Correct path for app/database/models
            ]

            # İlk bulunan path'i kullan
            yolo_model_path = None
            for path in possible_paths:
                resolved_path = path.resolve()
                print(f"🔍 Model aranıyor: {resolved_path}")
                if resolved_path.exists():
                    yolo_model_path = resolved_path
                    print(f"✅ Model bulundu: {yolo_model_path}")
                    break

            # Model yoksa huggingface'den indirmeyi veya cache'den kullanmayı dene
            if not yolo_model_path:
                print(f"☁️ Yerel YOLO model bulunamadı, HuggingFace Hub önbelleği kontrol ediliyor...")
                try:
                    from huggingface_hub import hf_hub_download
                    weight_path = hf_hub_download(
                        repo_id="juliozhao/DocLayout-YOLO-DocStructBench",
                        filename="doclayout_yolo_docstructbench_imgsz1024.pt",
                    )
                    yolo_model_path = Path(weight_path)
                    print(f"✅ Model HuggingFace önbelleğinden bulundu: {yolo_model_path}")
                except Exception as e:
                    print(f"❌ YOLO modeli ne yerelde ne de HuggingFace'de bulunamadı: {e}")
                    
                    # Eğer tamamen başarısız olursa uyarı yapıp dön
                    print(f"\n⚠️  Gazete tespiti çalışmayacak (normal OCR devam edecek)")
                    self.gazete_processor = None
                    return

            # Gazete processor oluştur - UPDATED: Surya Layout desteği
            # layout_engine: "surya" veya "yolo" seçilebilir
            self.gazete_processor = GazeteOCRProcessor(
                yolo_model_path=str(yolo_model_path),
                recognizer=self.recognizer,
                detector=self.detector,
                layout_predictor=self.layout_predictor,  # Surya LayoutPredictor
                layout_engine="surya"  # "surya" veya "yolo" - varsayılan olarak Surya kullan
            )

            print("✅ Gazete processor hazır")
            print(f"   YOLO Model: {yolo_model_path.name}")
            print(f"   Boyut: {yolo_model_path.stat().st_size / (1024 * 1024):.1f} MB")
            print(f"   Layout Engine: SURYA (Surya LayoutPredictor)")

        except Exception as e:
            print(f"❌ Gazete processor başlatılamadı: {e}")
            import traceback
            print(f"📋 Detaylı hata:")
            print(traceback.format_exc())
            self.gazete_processor = None
    
    def clear_gpu_cache(self):
        """GPU belleğini temizle - Büyük dosyalar arasında çağrılmalı"""
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
            print("🧹 GPU cache temizlendi")

    def get_gpu_status(self) -> dict:
        """Anlık GPU durumunu döndür"""
        if not torch.cuda.is_available():
            return {'status': 'CPU mode'}

        return {
            'device': str(self.device),
            'name': self.gpu_info.get('name', 'Unknown'),
            'total_memory_gb': self.gpu_info.get('memory_gb', 0),
            'allocated_mb': torch.cuda.memory_allocated() / 1e6,
            'reserved_mb': torch.cuda.memory_reserved() / 1e6,
            'utilization_percent': (torch.cuda.memory_allocated() / (self.gpu_info.get('memory_gb', 1) * 1e9)) * 100,
            'optimal_batch_size': getattr(self, 'optimal_batch_size', 12),
            'amp_enabled': getattr(self, 'use_amp', False),
            'generation': self.gpu_info.get('generation', 'Unknown')
        }

    def warmup_gpu(self):
        """GPU'yu ısıt - İlk inference'dan önce CUDA lazy init'i tetikler"""
        if not torch.cuda.is_available():
            return
        print("🔥 GPU warmup başlıyor...")
        with torch.inference_mode():
            x = torch.randn(1, 3, 1024, 1024, device=self.device)
            _ = torch.nn.functional.interpolate(x, size=(512, 512), mode='bilinear')
            torch.cuda.synchronize()
        torch.cuda.empty_cache()
        print("✅ GPU warmup tamamlandı")

    def _setup_gpu_optimization(self):
        """RTX 5000 Ada / Blackwell için Yüksek Performanslı GPU Ayarları"""
        try:
            import torch

            if torch.cuda.is_available():
                # NVIDIA GPU'yu zorla seç
                device_count = torch.cuda.device_count()
                print(f"🔍 Bulunan CUDA device sayısı: {device_count}")

                best_device = 0
                best_score = 0
                for i in range(device_count):
                    props = torch.cuda.get_device_properties(i)
                    if "NVIDIA" in props.name:
                        score = (props.major * 10 + props.minor) * 100 + (props.total_memory / 1e9)
                        if score > best_score:
                            best_score = score
                            best_device = i

                torch.cuda.set_device(best_device)
                self.device = torch.device(f"cuda:{best_device}")

                props = torch.cuda.get_device_properties(best_device)
                gpu_name = props.name
                memory_gb = props.total_memory / 1e9
                compute_cap = (props.major, props.minor)

                print(f"🎮 Seçilen GPU: {gpu_name} ({memory_gb:.1f}GB)")
                print(f"   Compute Capability: {compute_cap}")

                # --- GPU Nesil Tespiti ---
                is_blackwell = props.major >= 10
                is_ada_lovelace = props.major == 8 and props.minor >= 9
                is_ampere = props.major == 8 and props.minor < 9
                is_modern_gpu = props.major >= 8

                if is_blackwell:
                    gpu_gen = "Blackwell"
                elif is_ada_lovelace:
                    gpu_gen = "Ada Lovelace"
                elif is_ampere:
                    gpu_gen = "Ampere"
                else:
                    gpu_gen = "Legacy"
                print(f"   Nesil: {gpu_gen}")

                # --- 1. TensorFloat-32 (TF32) ---
                if is_modern_gpu:
                    torch.set_float32_matmul_precision('high')
                    torch.backends.cuda.matmul.allow_tf32 = True
                    torch.backends.cudnn.allow_tf32 = True
                    print("✅ TF32 etkinleştirildi")

                # --- 2. cuDNN Benchmark ---
                torch.backends.cudnn.benchmark = True
                torch.backends.cudnn.deterministic = False
                print("✅ cuDNN Benchmark aktif")

                # --- 3. Flash Attention (Ada/Blackwell) ---
                if is_ada_lovelace or is_blackwell:
                    if hasattr(torch.backends.cuda, 'enable_flash_sdp'):
                        torch.backends.cuda.enable_flash_sdp(True)
                        print("✅ Flash Attention etkinleştirildi")
                    if hasattr(torch.backends.cuda, 'enable_mem_efficient_sdp'):
                        torch.backends.cuda.enable_mem_efficient_sdp(True)
                        print("✅ Memory-Efficient Attention etkinleştirildi")

                # --- 4. Bellek Yönetimi ---
                if is_blackwell:
                    alloc_conf = "expandable_segments:True,garbage_collection_threshold:0.9"
                elif is_ada_lovelace:
                    alloc_conf = "expandable_segments:True,garbage_collection_threshold:0.85"
                elif is_ampere:
                    alloc_conf = "expandable_segments:True,max_split_size_mb:512"
                else:
                    alloc_conf = "max_split_size_mb:256"
                os.environ["PYTORCH_CUDA_ALLOC_CONF"] = alloc_conf
                print(f"✅ Bellek: {alloc_conf}")

                # --- 5. Cache Temizliği ---
                torch.cuda.empty_cache()

                # --- 6. Optimal Batch Size ---
                if is_blackwell:
                    self.optimal_batch_size = 24
                elif is_ada_lovelace:
                    self.optimal_batch_size = 16 if memory_gb >= 32 else 12
                elif is_ampere:
                    self.optimal_batch_size = 12
                else:
                    self.optimal_batch_size = 8
                print(f"✅ Optimal batch size: {self.optimal_batch_size}")

                # --- 7. AMP (Automatic Mixed Precision) ---
                self.use_amp = is_modern_gpu
                if is_modern_gpu:
                    self.amp_dtype = torch.bfloat16 if (is_ada_lovelace or is_blackwell) else torch.float16
                    print(f"✅ AMP etkin: {self.amp_dtype}")
                else:
                    self.amp_dtype = torch.float32

                # --- GPU Bilgileri ---
                self.gpu_info = {
                    'device': str(self.device),
                    'name': gpu_name,
                    'memory_gb': memory_gb,
                    'compute_capability': compute_cap,
                    'generation': gpu_gen,
                    'optimal_batch_size': self.optimal_batch_size
                }

                print(f"🚀 GPU Optimizasyonu tamamlandı!")

            else:
                print("⚠️ CUDA bulunamadı, CPU kullanılacak")
                self.device = torch.device("cpu")
                self.optimal_batch_size = 4
                self.use_amp = False
                self.amp_dtype = torch.float32
                self.gpu_info = {'device': 'cpu', 'name': 'CPU', 'memory_gb': 0}

        except Exception as e:
            print(f"⚠️ GPU setup hatası: {e}")
            self.device = torch.device("cpu")
            self.optimal_batch_size = 4
            self.use_amp = False
            self.amp_dtype = torch.float32
            self.gpu_info = {'device': 'cpu', 'name': 'CPU', 'memory_gb': 0}

    def _load_models(self):
        """Surya v0.17+ için modelleri hazırla ve GPU'ya yükle"""
        import torch

        print(f"📦 Modeller yükleniyor... (API: {SURYA_API})")
        print(f"🎯 Hedef device: {self.device}")

        self.has_detection = False
        self.has_recognition = False
        self.has_layout = False
        self.supported_languages = ["tr", "en", "ar"]
        self.foundation = None
        self.layout_foundation = None

        if SURYA_API == "new":
            # Surya settings import
            try:
                from surya.settings import settings as surya_settings
            except ImportError:
                surya_settings = None
                print("⚠️ surya.settings import edilemedi")

            # ═══════════════════════════════════════════════════════════════
            # 1. DETECTION PREDICTOR (Foundation gerektirmez)
            # ═══════════════════════════════════════════════════════════════
            try:
                self.detector = DetectionPredictor()
                
                if hasattr(self.detector, 'model') and hasattr(self.detector.model, 'to'):
                    self.detector.model.to(self.device)
                    print(f"📱 Detection Model GPU'ya taşındı: {self.device}")
                
                self.has_detection = True
                print("✅ DetectionPredictor hazır (GPU)")
            except Exception as e:
                self.detector = None
                print(f"⚠️ DetectionPredictor yüklenemedi: {e}")

            # ═══════════════════════════════════════════════════════════════
            # 2. FOUNDATION PREDICTOR (Recognition için)
            # ═══════════════════════════════════════════════════════════════
            try:
                from surya.foundation import FoundationPredictor
                
                self.foundation = FoundationPredictor()
                
                if hasattr(self.foundation, 'model') and hasattr(self.foundation.model, 'to'):
                    self.foundation.model.to(self.device)
                    print(f"📱 Foundation Model GPU'ya taşındı: {self.device}")
                
                print("✅ FoundationPredictor hazır (Recognition için)")
            except Exception as e:
                print(f"⚠️ FoundationPredictor oluşturulamadı: {e}")
                self.foundation = None

            # ═══════════════════════════════════════════════════════════════
            # 3. RECOGNITION PREDICTOR
            # ═══════════════════════════════════════════════════════════════
            if self.foundation is not None:
                try:
                    self.recognizer = RecognitionPredictor(self.foundation)
                    self.has_recognition = True
                    print("✅ RecognitionPredictor hazır (GPU)")
                except Exception as e:
                    print(f"⚠️ RecognitionPredictor başarısız: {e}")
                    self.has_recognition = False

            # ═══════════════════════════════════════════════════════════════
            # 4. LAYOUT PREDICTOR (Ayrı FoundationPredictor + LAYOUT_MODEL_CHECKPOINT)
            # ═══════════════════════════════════════════════════════════════
            if LAYOUT_AVAILABLE:
                try:
                    from surya.foundation import FoundationPredictor
                    from surya.layout import LayoutPredictor
                    
                    # Layout için ayrı Foundation (LAYOUT_MODEL_CHECKPOINT ile)
                    layout_checkpoint = None
                    if surya_settings and hasattr(surya_settings, 'LAYOUT_MODEL_CHECKPOINT'):
                        layout_checkpoint = surya_settings.LAYOUT_MODEL_CHECKPOINT
                        print(f"📋 Layout checkpoint: {layout_checkpoint}")
                    
                    if layout_checkpoint:
                        self.layout_foundation = FoundationPredictor(checkpoint=layout_checkpoint)
                    else:
                        # Checkpoint yoksa varsayılan kullan
                        self.layout_foundation = FoundationPredictor()
                    
                    if hasattr(self.layout_foundation, 'model') and hasattr(self.layout_foundation.model, 'to'):
                        self.layout_foundation.model.to(self.device)
                        print(f"📱 Layout Foundation GPU'ya taşındı: {self.device}")
                    
                    # LayoutPredictor oluştur
                    self.layout_predictor = LayoutPredictor(self.layout_foundation)
                    
                    self.has_layout = True
                    print("✅ LayoutPredictor hazır (GPU)")
                    
                except Exception as e:
                    print(f"⚠️ LayoutPredictor yüklenemedi: {e}")
                    import traceback
                    traceback.print_exc()
                    self.has_layout = False
            else:
                print("⚠️ LayoutPredictor modülü import edilemedi")
                self.has_layout = False

        elif SURYA_API == "old":
            self.has_detection = True
            self.has_recognition = True
            self.has_layout = False
            print("📦 Eski API kullanılıyor (v0.16 ve öncesi)")

        # ═══════════════════════════════════════════════════════════════
        # Final Durum Raporu
        # ═══════════════════════════════════════════════════════════════
        print(f"🔥 GPU Durumu:")
        if torch.cuda.is_available():
            print(f"   Current Device: {torch.cuda.current_device()}")
            print(f"   Device Name: {torch.cuda.get_device_name()}")
            print(f"   Memory: {torch.cuda.memory_allocated() / 1e6:.1f}MB allocated")
        
        print(f"📊 Özellikler - Detection: {self.has_detection}, Recognition: {self.has_recognition}, Layout: {self.has_layout}")

    def pdf_to_images(self, pdf_path: str) -> List[Image.Image]:
        """PDF dosyasını sayfa sayfa Image listesine çevir"""
        images = []

        try:
            pdf_document = fitz.open(pdf_path)

            for page_num in range(pdf_document.page_count):
                page = pdf_document[page_num]

                # Yüksek çözünürlük için zoom
                zoom = 3.3
                matrix = fitz.Matrix(zoom, zoom)
                pixmap = page.get_pixmap(matrix=matrix)

                # PIL Image'e çevir
                img_data = pixmap.tobytes("ppm")
                img = Image.open(BytesIO(img_data))

                # RGB'ye çevir (RGBA varsa)
                if img.mode != 'RGB':
                    img = img.convert('RGB')

                images.append(img)

            pdf_document.close()
            print(f"📄 PDF işlendi: {len(images)} sayfa")

        except Exception as e:
            print(f"❌ PDF işleme hatası: {e}")
            raise

        return images

    def analyze_layout(self, image, page_number=1):
        """
        Surya v0.17.0+ için layout analizi.
        LayoutBox.polygon kullanır (PolygonBox'tan miras).
        """
        if not self.has_layout:
            print("⚠️ Layout predictor aktif değil")
            return None

        with self.layout_lock:
            try:
                actual_w, actual_h = image.size
                print(f"📐 Görüntü boyutu: {actual_w}x{actual_h}")

                with torch.inference_mode():
                    layout_results = self.layout_predictor([image])

                if not layout_results or len(layout_results) == 0:
                    print("⚠️ Layout sonucu boş")
                    return None

                layout = layout_results[0]

                # image_bbox'tan referans boyut al [x1, y1, x2, y2] formatında
                ref_w, ref_h = actual_w, actual_h
                if hasattr(layout, 'image_bbox') and layout.image_bbox:
                    img_bbox = layout.image_bbox
                    # image_bbox = [0, 0, width, height] formatında
                    if len(img_bbox) >= 4:
                        ref_w = img_bbox[2] - img_bbox[0]  # x2 - x1
                        ref_h = img_bbox[3] - img_bbox[1]  # y2 - y1
                        print(f"📐 Layout referans boyut: {ref_w}x{ref_h}")

                # Ölçeklendirme faktörü
                scale_w = actual_w / ref_w if ref_w > 0 else 1.0
                scale_h = actual_h / ref_h if ref_h > 0 else 1.0
                
                needs_scaling = abs(scale_w - 1.0) > 0.01 or abs(scale_h - 1.0) > 0.01
                if needs_scaling:
                    print(f"📐 Ölçek faktörü: {scale_w:.4f}x{scale_h:.4f}")

                page_layout = {
                    'page_number': page_number,
                    'headings': [],
                    'paragraphs': [],
                    'text_blocks': [],
                    'reading_order': []
                }

                if not hasattr(layout, 'bboxes') or not layout.bboxes:
                    print("⚠️ Layout bboxes bulunamadı")
                    return page_layout

                print(f"📋 Layout: {len(layout.bboxes)} element bulundu")

                for i, item in enumerate(layout.bboxes):
                    # Label al
                    label = getattr(item, 'label', 'Text') or 'Text'
                    
                    # Position al (okuma sırası için)
                    position = getattr(item, 'position', i)
                    
                    # Confidence/top_k al
                    confidence = 1.0
                    if hasattr(item, 'top_k') and item.top_k:
                        # top_k dict'inden en yüksek değeri al
                        confidence = max(item.top_k.values()) if item.top_k else 1.0
                    
                    # ═══════════════════════════════════════════════════════════
                    # POLYGON'dan BBOX oluştur (Surya v0.17+ için kritik!)
                    # LayoutBox, PolygonBox'tan miras alır ve polygon attribute'u var
                    # ═══════════════════════════════════════════════════════════
                    final_bbox = None
                    
                    # Önce polygon dene (PolygonBox'tan miras)
                    if hasattr(item, 'polygon') and item.polygon:
                        poly = item.polygon
                        if poly and len(poly) >= 4:
                            # Polygon: [(x1,y1), (x2,y2), (x3,y3), (x4,y4)]
                            x_coords = [p[0] for p in poly]
                            y_coords = [p[1] for p in poly]
                            
                            raw_bbox = [
                                min(x_coords),
                                min(y_coords),
                                max(x_coords),
                                max(y_coords)
                            ]
                            
                            # Ölçeklendir (gerekirse)
                            if needs_scaling:
                                final_bbox = [
                                    raw_bbox[0] * scale_w,
                                    raw_bbox[1] * scale_h,
                                    raw_bbox[2] * scale_w,
                                    raw_bbox[3] * scale_h
                                ]
                            else:
                                final_bbox = raw_bbox
                            
                            if i < 5:
                                print(f"   [{i}] {label} (pos:{position}) polygon -> bbox: {[int(x) for x in final_bbox]}")
                    
                    # Polygon yoksa bbox attribute dene (fallback)
                    if final_bbox is None and hasattr(item, 'bbox') and item.bbox:
                        raw_bbox = list(item.bbox)
                        if needs_scaling:
                            final_bbox = [
                                raw_bbox[0] * scale_w,
                                raw_bbox[1] * scale_h,
                                raw_bbox[2] * scale_w,
                                raw_bbox[3] * scale_h
                            ]
                        else:
                            final_bbox = raw_bbox
                        
                        if i < 5:
                            print(f"   [{i}] {label} bbox: {[int(x) for x in final_bbox]}")

                    if final_bbox is None:
                        print(f"   ⚠️ Element {i}: Koordinat bulunamadı, atlanıyor")
                        continue

                    # Sınır kontrolü
                    final_bbox = [
                        max(0, min(final_bbox[0], actual_w)),
                        max(0, min(final_bbox[1], actual_h)),
                        max(0, min(final_bbox[2], actual_w)),
                        max(0, min(final_bbox[3], actual_h))
                    ]

                    element = {
                        'id': i + 1,
                        'bbox': final_bbox,
                        'type': label,
                        'position': position,
                        'confidence': confidence
                    }

                    # Kategorizasyon (label'a göre)
                    label_lower = label.lower()
                    if any(x in label_lower for x in ['title', 'header', 'heading', 'section']):
                        page_layout['headings'].append(element)
                    elif any(x in label_lower for x in ['text', 'paragraph', 'list', 'plain', 'caption', 'footnote']):
                        page_layout['paragraphs'].append(element)
                    else:
                        page_layout['text_blocks'].append(element)

                # Okuma sırası (position'a göre veya y-koordinatına göre)
                all_elements = page_layout['headings'] + page_layout['paragraphs'] + page_layout['text_blocks']
                all_elements.sort(key=lambda x: (x.get('position', 0), x['bbox'][1], x['bbox'][0]))
                page_layout['reading_order'] = [e['id'] for e in all_elements]

                print(f"✅ Layout analizi tamamlandı: {len(all_elements)} element")
                print(f"   Headings: {len(page_layout['headings'])}, Paragraphs: {len(page_layout['paragraphs'])}, Other: {len(page_layout['text_blocks'])}")
                
                return page_layout

            except Exception as e:
                print(f"❌ Layout Analiz Hatası: {e}")
                import traceback
                traceback.print_exc()
                return None
            
    def _predict_labels_from_positions(self, bboxes, page_idx=0):
        """
        Layout predictor labels döndürmediğinde, bbox pozisyonlarından
        başlık/paragraf tahmini yapar.
        """
        if not bboxes:
            return []

        labels = []

        # Bbox'ları y koordinatına göre sırala
        sorted_bboxes = []
        for i, bbox in enumerate(bboxes):
            try:
                if hasattr(bbox, 'tolist'):
                    bbox_list = bbox.tolist()
                elif isinstance(bbox, (list, tuple)):
                    # Nested tuple/list kontrolü
                    if len(bbox) >= 4:
                        bbox_list = []
                        for coord in bbox:
                            if isinstance(coord, (list, tuple)):
                                # Eğer koordinat da tuple/list ise ilkini al
                                bbox_list.append(float(coord[0]) if len(coord) > 0 else 0.0)
                            else:
                                bbox_list.append(float(coord))
                    else:
                        bbox_list = [0, 0, 0, 0]
                else:
                    # Tek değer ise string'e çevir
                    coord_str = str(bbox)
                    # Parantezleri temizle ve virgülle ayır
                    coord_str = coord_str.strip('()[]').replace(' ', '')
                    coords = coord_str.split(',')
                    if len(coords) >= 4:
                        bbox_list = [float(c) for c in coords[:4]]
                    else:
                        bbox_list = [0, 0, 0, 0]

                # Bbox geçerli mi kontrol et
                if len(bbox_list) >= 4:
                    sorted_bboxes.append((i, bbox_list))
                else:
                    print(f"   ⚠️ Geçersiz bbox {i}: {bbox}")
                    sorted_bboxes.append((i, [0, 0, 0, 0]))

            except Exception as e:
                print(f"   ❌ Bbox {i} parse hatası: {e}, bbox: {bbox}")
                sorted_bboxes.append((i, [0, 0, 0, 0]))

        if not sorted_bboxes:
            return ["text"] * len(bboxes)

        # Y koordinatına göre sırala
        sorted_bboxes.sort(key=lambda x: x[1][1])  # y coordinate

        # Yükseklik ve genişlik istatistikleri
        heights = [abs(bbox[3] - bbox[1]) for _, bbox in sorted_bboxes]
        widths = [abs(bbox[2] - bbox[0]) for _, bbox in sorted_bboxes]

        avg_height = sum(heights) / len(heights) if heights else 20
        avg_width = sum(widths) / len(widths) if widths else 100

        print(f"   📏 Ortalama yükseklik: {avg_height:.1f}, genişlik: {avg_width:.1f}")

        # Her bbox için tahmin yap
        for idx, (original_idx, bbox) in enumerate(sorted_bboxes):
            x1, y1, x2, y2 = bbox
            width = abs(x2 - x1)
            height = abs(y2 - y1)

            # Başlık tahmini kriterleri:
            # 1. Sayfanın üst %30'unda ise
            # 2. Ortalamadan büyük font (yükseklik) ise
            # 3. Merkeze yakın ise
            # 4. İlk birkaç elementten biri ise

            is_heading = False
            reasons = []

            # Pozisyon kontrolü (ilk 3 element)
            if idx < 3:
                is_heading = True
                reasons.append("üst_pozisyon")

            # Yükseklik kontrolü (ortalamadan %20 büyük)
            if height > avg_height * 1.2:
                is_heading = True
                reasons.append("büyük_font")

            # Genişlik kontrolü (dar elementler başlık olabilir)
            if width < avg_width * 0.7:
                is_heading = True
                reasons.append("dar_genişlik")

            # Merkez kontrolü (sayfa genişliğinin ortasına yakın)
            center_x = (x1 + x2) / 2
            if idx == 0:  # İlk element genelde başlık
                is_heading = True
                reasons.append("ilk_element")

            if is_heading:
                labels.append("title")
                print(f"     Bbox {original_idx}: BAŞLIK tahmini ({', '.join(reasons)})")
            else:
                labels.append("text")
                print(f"     Bbox {original_idx}: PARAGRAF tahmini")

        # Orijinal sıraya geri dön
        result_labels = ["text"] * len(bboxes)
        for (original_idx, _), predicted_label in zip(sorted_bboxes, labels):
            if 0 <= original_idx < len(result_labels):
                result_labels[original_idx] = predicted_label

        return result_labels

    def detect_text_regions(self, images):
        """
        UI 'text_regions' bekliyor ve her bölgede 'region_id' ile 'confidence' alanlarına bakıyor.
        Bu fonksiyon çıktıyı UI ile birebir uyumlu hale getirir.
        """
        print("🔎 Detection başlıyor... (API:", SURYA_API, ")")
        pages = []

        if SURYA_API == "new":
            if not self.has_detection:
                raise RuntimeError("DetectionPredictor yok")

            preds = self.detector(images)
            for page_idx, pred in enumerate(preds):
                text_regions = []
                # API'de skor/olasılık alanı sürüme göre değişebilir; mevcut değilse 1.0 veriyoruz.
                # BBox erişimi: objede .bbox ya da doğrudan tuple/list olabilir.
                bboxes = getattr(pred, "bboxes", None)
                scores = getattr(pred, "scores", None) or getattr(pred, "confidences", None)

                if bboxes:
                    for i, box in enumerate(bboxes):
                        if hasattr(box, "bbox"):
                            coords = box.bbox.tolist() if hasattr(box.bbox, "tolist") else list(box.bbox)
                        else:
                            coords = list(box) if isinstance(box, (list, tuple)) else []
                        conf = None
                        try:
                            conf = float(scores[i]) if scores is not None else 1.0
                        except Exception:
                            conf = 1.0

                        text_regions.append({
                            "region_id": i + 1,
                            "confidence": conf,
                            "bbox": coords
                        })

                pages.append({
                    "page_number": page_idx + 1,
                    "text_regions": text_regions,  # 👈 UI'nin beklediği isim
                    "region_count": len(text_regions)
                })

        elif SURYA_API == "old":
            det = batch_text_detection(images)
            for page_idx, page in enumerate(det):
                text_regions = []
                for i, region in enumerate(page.get("bboxes", [])):
                    coords = list(region)
                    text_regions.append({
                        "region_id": i + 1,
                        "confidence": 1.0,  # eski API için tahmini
                        "bbox": coords
                    })
                pages.append({
                    "page_number": page_idx + 1,
                    "text_regions": text_regions,
                    "region_count": len(text_regions)
                })
        else:
            raise RuntimeError("SuryaOCR yok")

        print("✅ Detection tamam")
        return pages

    def _group_with_bbox_analysis(self, lines, boxes):
        """Mevcut bbox tabanlı gruplama (optimize edilmiş)"""

        # Mevcut group_lines_into_paragraphs metodundaki kodu kullan
        # Ama biraz daha optimize et

        def _append_line(acc, s):
            if not acc:
                acc.append(s)
                return
            prev = acc[-1]
            if prev.rstrip().endswith(('-', '–', '—', '―')):
                acc[-1] = prev.rstrip('- –—―').rstrip() + s.lstrip()
            else:
                acc[-1] = prev + ' ' + s

        def _is_page_number(txt):
            t = txt.strip()
            if t.isdigit() and 1 <= int(t) <= 9999:
                return True
            if re.match(r'^[IVXLCDMivxlcdm]+$', t):
                return True
            return False

        def _is_likely_heading(txt, height=None, avg_height=None):
            t = txt.strip()
            if not t or _is_page_number(t):
                return False

            word_count = len(t.split())
            char_count = len(t)

            if not (1 <= word_count <= 5 and 3 <= char_count <= 80):
                return False

            if height and avg_height:
                if not (t.isupper() or height > avg_height * 1.3):
                    return False
            else:
                if not t.isupper():
                    return False

            if t[0].isupper() and not t.endswith(('.', '!', '?', ';', ':')):
                return True

            if t.isupper() and word_count <= 6:
                return True

            return False

        paragraphs, current = [], []

        if boxes and len(boxes) == len(lines):
            # Bbox ile gelişmiş analiz
            pairs = [(t, b) for t, b in zip(lines, boxes) if b and len(b) >= 4]
            if pairs:
                pairs.sort(key=lambda p: (p[1][1], p[1][0]))
                lines = [p[0] for p in pairs]
                boxes = [p[1] for p in pairs]

                heights = [max(1.0, bb[3] - bb[1]) for bb in boxes]
                avg_h = sum(heights) / len(heights) if heights else 18.0

                for i, (txt, bb) in enumerate(zip(lines, boxes)):
                    t = (txt or "").strip()
                    if not t or _is_page_number(t):
                        if current:
                            paragraphs.append(" ".join(current))
                            current = []
                        continue

                    line_height = heights[i]
                    is_heading = _is_likely_heading(t, line_height, avg_h)

                    vgap_prev = boxes[i][1] - boxes[i - 1][3] if i > 0 else 50

                    new_para = (i == 0 or
                                is_heading or
                                vgap_prev >= avg_h * 1.5)

                    if new_para:
                        if current:
                            paragraphs.append(" ".join(current))
                            current = []

                        if is_heading:
                            paragraphs.append(f"## {t}")
                        else:
                            current = [t]
                    else:
                        _append_line(current, t)

                if current:
                    paragraphs.append(" ".join(current))
        else:
            # Basit analiz
            for i, raw in enumerate(lines):
                t = (raw or "").strip()
                if not t or _is_page_number(t):
                    if current:
                        paragraphs.append(" ".join(current))
                        current = []
                    continue

                is_heading = _is_likely_heading(t)
                new_para = (i == 0 or is_heading)

                if new_para:
                    if current:
                        paragraphs.append(" ".join(current))
                        current = []

                    if is_heading:
                        paragraphs.append(f"## {t}")
                    else:
                        current = [t]
                else:
                    _append_line(current, t)

            if current:
                paragraphs.append(" ".join(current))

        return [p for p in paragraphs if p.strip()]

    def _calculate_bbox_overlap(self, bbox1, bbox2):
        """İki bbox arasındaki overlap oranını hesaplar"""
        x1_min, y1_min, x1_max, y1_max = bbox1
        x2_min, y2_min, x2_max, y2_max = bbox2

        # Intersection hesapla
        x_overlap = max(0, min(x1_max, x2_max) - max(x1_min, x2_min))
        y_overlap = max(0, min(y1_max, y2_max) - max(y1_min, y2_min))

        intersection = x_overlap * y_overlap

        # Areas hesapla
        area1 = (x1_max - x1_min) * (y1_max - y1_min)
        area2 = (x2_max - x2_min) * (y2_max - y2_min)

        if area1 == 0:
            return 0

        return intersection / area1

    def _group_with_enhanced_bbox_analysis(self, lines, boxes):
        """
        Geliştirilmiş bbox tabanlı gruplama - pozisyon ve font analizi
        Hyphenation iyileştirmeleri:
          - ASCII '-' yanında soft hyphen (\u00AD), non-breaking hyphen (\u2011),
            figure/short/long dashes (\u2010, \u2012, \u2013, \u2014, \u2015) desteklenir.
          - Post-processing: yalnızca 'harf + (tire) + boşluk + küçük harf' ve
            TİRENİN SOLUNDA BOŞLUK OLMAYAN durumları birleştir (kelime bölmesi).
          - Soft hyphen ve zero-width boşluklar temizlenir.
        """
        import statistics
        import re

        _LOWER_LETTERS = r"a-zçğıöşüà-žµß-öø-ÿ"
        _HYPHENS = "\u002d\u00ad\u2010\u2011\u2012\u2013\u2014\u2015"  # - SHY ‐ - ‒ – — ―

        def _strip_invisibles(s):
            if not s:
                return s
            return (s
                    .replace("\u00AD", "")  # soft hyphen
                    .replace("\u200B", "")  # zero-width space
                    .replace("\u200C", "")  # ZWNJ
                    .replace("\u200D", "")  # ZWJ
                    .replace("\u00A0", " ")  # NBSP -> space
                    )

        def _append_line_smart(current_lines, new_line):
            if not current_lines:
                current_lines.append(_strip_invisibles(new_line))
                return

            last_line = _strip_invisibles(current_lines[-1])
            new_line = _strip_invisibles(new_line)
            last_stripped = last_line.rstrip()
            new_stripped = new_line.strip()

            if re.search(rf"[{_HYPHENS}]\s*$", last_stripped):
                if new_stripped and new_stripped[0].islower():
                    current_lines[-1] = re.sub(rf"[{_HYPHENS}]\s*$", "", last_stripped) + new_stripped
                else:
                    current_lines[-1] = last_line + " " + new_stripped
            else:
                current_lines[-1] = last_line + " " + new_stripped

        def _is_page_number_advanced(txt):
            t = _strip_invisibles((txt or "")).strip()
            if not t:
                return False
            if t.isdigit() and 1 <= int(t) <= 9999:
                return True
            if re.match(r'^[IVXLCDMivxlcdm]+$', t):
                return True
            return False

        def _is_likely_heading_enhanced(txt, height=None, avg_height=None, position_score=0):
            t = _strip_invisibles((txt or "")).strip()
            if not t or _is_page_number_advanced(t):
                return False

            word_count = len(t.split())
            char_count = len(t)

            if not (1 <= word_count <= 12 and 3 <= char_count <= 150):
                return False

            score = 0

            if height and avg_height:
                if height > avg_height * 1.4:
                    score += 4
                elif height > avg_height * 1.2:
                    score += 2
                elif height > avg_height * 1.1:
                    score += 1

            score += position_score

            if t.isupper():
                score += 3

            if t[0].isupper() and not t.endswith(('.', '!', '?', ';', ':')):
                score += 2

            heading_patterns = [
                r'^[A-ZÇĞIİÖŞÜ][A-ZÇĞIİÖŞÜ\s]{5,}$',
                r'^BAB\s+[IVXLCDM]+',
                r'^BÖLÜM\s+\d+',
                r'^FASIL\s+[IVXLCDM]+',
                r'^\d+\.\s*[A-ZÇĞIİÖŞÜ]',
                r'^KISIM\s*\d*',
            ]

            for pattern in heading_patterns:
                if re.match(pattern, t, re.IGNORECASE):
                    score += 3
                    break

            return score >= 4

        def _is_continuation_line(current_line, prev_line):
            if not prev_line or not current_line:
                return False

            prev_stripped = _strip_invisibles(prev_line).rstrip()
            current_stripped = _strip_invisibles(current_line).strip()

            if re.search(rf"[{_HYPHENS}]\s*$", prev_stripped):
                return True
            if prev_stripped.endswith(','):
                return True
            if prev_stripped.endswith(';'):
                return True
            if prev_stripped.endswith(':'):
                return True
            if (current_stripped and current_stripped[0].islower() and
                    not prev_stripped.endswith(('.', '!', '?'))):
                return True

            conjunction_endings = ['ve', 'veya', 'ile', 'da', 'de', 'ki', 'ama', 'fakat', 'ancak', 'lakin']
            prev_words = prev_stripped.split()
            if prev_words and prev_words[-1].lower() in conjunction_endings:
                return True

            return False

        def _fix_intraword_hyphen_splits(text):
            """
            Paragraf içinde kalan kelime-bölmesi kalıplarını birleştir:
              [harf][tire][boşluk][küçük harf]  (sol bitişik!)
            Örn: 'yap- tığım' -> 'yaptığım'
            NOT: 'a - i' gibi (solunda boşluk olan) anlamsal tirelere DOKUNMAZ.
            """
            if not text:
                return text
            t = _strip_invisibles(text)
            pattern = re.compile(
                rf"([{_LOWER_LETTERS}])[{_HYPHENS}]\s+([{_LOWER_LETTERS}])",
                re.UNICODE
            )
            for _ in range(3):
                t_new = pattern.sub(r"\1\2", t)
                if t_new == t:
                    break
                t = t_new
            return t

        paragraphs, current = [], []

        if boxes and len(boxes) == len(lines):
            print("   📏 Gelişmiş bbox analizi yapılıyor...")

            pairs = [(_strip_invisibles(t), b) for t, b in zip(lines, boxes) if b and len(b) >= 4]
            if pairs:
                pairs.sort(key=lambda p: (p[1][1], p[1][0]))
                lines = [p[0] for p in pairs]
                boxes = [p[1] for p in pairs]

                heights = [max(1.0, bb[3] - bb[1]) for bb in boxes]
                y_positions = [bb[1] for bb in boxes]

                avg_h = sum(heights) / len(heights) if heights else 18.0
                min_y = min(y_positions) if y_positions else 0
                max_y = max(y_positions) if y_positions else 100
                page_height = max_y - min_y if max_y > min_y else 100

                print(f"     Ortalama yükseklik: {avg_h:.1f}, sayfa yüksekliği: {page_height:.1f}")

                for i, (txt, bb) in enumerate(zip(lines, boxes)):
                    t = (txt or "").strip()

                    if _is_page_number_advanced(t):
                        if current:
                            paragraphs.append(" ".join(current))
                            current = []
                        continue

                    if not t:
                        if current:
                            paragraphs.append(" ".join(current))
                            current = []
                        continue

                    line_height = heights[i]
                    y_pos = bb[1]

                    relative_position = (y_pos - min_y) / page_height if page_height > 0 else 0
                    position_score = 0

                    if relative_position < 0.15:
                        position_score = 9
                    elif relative_position < 0.3:
                        position_score = 6
                    elif i < 5:
                        position_score = 4

                    is_heading = _is_likely_heading_enhanced(t, line_height, avg_h, position_score)

                    vgap_prev = bb[1] - boxes[i - 1][3] if i > 0 else 50

                    is_continuation = False
                    if i > 0:
                        prev_text = (lines[i - 1] or "").strip()
                        is_continuation = _is_continuation_line(t, prev_text)

                    new_para = (i == 0 or
                                is_heading or
                                (vgap_prev >= avg_h * 1.8 and not is_continuation))

                    if new_para:
                        if current:
                            combined_text = " ".join(current)
                            if not _is_page_number_advanced(combined_text):
                                paragraphs.append(combined_text)
                            current = []

                        if is_heading:
                            paragraphs.append(f"## {t}")
                        else:
                            current = [t]
                    else:
                        _append_line_smart(current, t)

                if current:
                    combined_text = " ".join(current)
                    if not _is_page_number_advanced(combined_text):
                        paragraphs.append(combined_text)
        else:
            print("   📝 Basit metin analizi yapılıyor...")
            cleaned_lines = [_strip_invisibles(x) for x in lines]
            for i, raw in enumerate(cleaned_lines):
                t = (raw or "").strip()

                if _is_page_number_advanced(t):
                    if current:
                        paragraphs.append(" ".join(current))
                        current = []
                    continue

                if not t:
                    if current:
                        paragraphs.append(" ".join(current))
                        current = []
                    continue

                position_score = 8 if i < 3 else 2 if i < 6 else 0
                is_heading = _is_likely_heading_enhanced(t, position_score=position_score)

                is_continuation = False
                if i > 0:
                    prev_text = (cleaned_lines[i - 1] or "").strip()
                    is_continuation = _is_continuation_line(t, prev_text)

                new_para = (i == 0 or is_heading and not is_continuation)

                if new_para:
                    if current:
                        combined_text = " ".join(current)
                        if not _is_page_number_advanced(combined_text):
                            paragraphs.append(combined_text)
                        current = []

                    if is_heading:
                        paragraphs.append(f"## {t}")
                    else:
                        current = [t]
                else:
                    _append_line_smart(current, t)

            if current:
                combined_text = " ".join(current)
                if not _is_page_number_advanced(combined_text):
                    paragraphs.append(combined_text)

        # Temizleme ve post-processing
        result = []
        for p in paragraphs:
            if p and p.strip():
                # ✅ OCR çıktısını temizle
                cleaned = self.clean_ocr_output(p.strip())

                # HTML/XML etiketlerini temizle (ekstra güvenlik)
                cleaned = re.sub(r'<[^>]+>', '', cleaned)

                # Çoklu boşlukları temizle
                cleaned = re.sub(r'\s+', ' ', cleaned)

                if cleaned and len(cleaned) > 2 and not _is_page_number_advanced(cleaned):
                    cleaned = _fix_intraword_hyphen_splits(cleaned)
                    result.append(cleaned)

        merged_result = []
        i = 0
        while i < len(result):
            current_para = result[i]

            if current_para.startswith('## '):
                merged_result.append(current_para)
                i += 1
                continue

            # Paragraf sonu tire birleştirmesi (kelime bölmesi durumu)
            if re.search(rf"[{_HYPHENS}]\s*$", current_para.rstrip()):
                if i + 1 < len(result) and not result[i + 1].startswith('## '):
                    merged = re.sub(rf"[{_HYPHENS}]\s*$", "", current_para.rstrip()) + result[i + 1].lstrip()
                    merged = _fix_intraword_hyphen_splits(merged)
                    merged_result.append(merged)
                    i += 2
                    continue

            merged_result.append(_fix_intraword_hyphen_splits(current_para))
            i += 1

        print(f"   ✅ {len(merged_result)} paragraf oluşturuldu (birleştirme sonrası)")
        return merged_result

    def _group_with_layout_analysis(self, lines, boxes, layout_info):
        """
        Layout analizi bilgisiyle paragraf gruplama - Layout analizi sonuçlarını doğru şekilde OCR satırlarıyla eşleştirip
        başlık ve paragraf ayırımını doğru yapan algoritma.
        """
        import re

        # Layout info kontrolü - liste mi dict mi?
        if isinstance(layout_info, list):
            if len(layout_info) == 0 or not layout_info[0]:
                print("   ⚠️ Layout info boş liste, bbox analizine geçiliyor")
                return self._group_with_enhanced_bbox_analysis(lines, boxes)
            # İlk sayfayı al
            page_layout = layout_info[0]
        elif isinstance(layout_info, dict):
            # Tek sayfa layout bilgisi
            page_layout = layout_info
        else:
            print("   ⚠️ Layout info formatı geçersiz, bbox analizine geçiliyor")
            return self._group_with_enhanced_bbox_analysis(lines, boxes)

        # İlk sayfanın layout bilgisini al
        page_layout = layout_info[0]
        all_elements = (page_layout.get('headings', []) +
                        page_layout.get('paragraphs', []) +
                        page_layout.get('text_blocks', []))

        if not all_elements:
            print("   ⚠️ Layout elementleri boş, bbox analizine geçiliyor")
            return self._group_with_enhanced_bbox_analysis(lines, boxes)

        print(f"   📖 Layout bilgisi kullanılıyor:")
        print(f"       Başlıklar: {len(page_layout.get('headings', []))}")
        print(f"       Paragraflar: {len(page_layout.get('paragraphs', []))}")
        print(f"       Metin blokları: {len(page_layout.get('text_blocks', []))}")

        # OCR satırlarını layout elementleriyle eşleştir
        element_to_lines = self._match_ocr_lines_to_layout(lines, boxes, all_elements)

        # OCR sequence'ını oluştur
        ocr_sequence = self._create_ocr_sequence(element_to_lines, all_elements)

        # Final paragrafları oluştur
        return self._process_ocr_sequence(ocr_sequence)

    def _match_ocr_lines_to_layout(self, lines, boxes, layout_elements):
        """
        OCR satırlarını layout elementleriyle eşleştir.
        """

        def _calculate_overlap(bbox1, bbox2):
            """İki bbox arasındaki overlap oranını hesaplar"""
            if not bbox1 or not bbox2 or len(bbox1) < 4 or len(bbox2) < 4:
                return 0

            x1_min, y1_min, x1_max, y1_max = bbox1[:4]
            x2_min, y2_min, x2_max, y2_max = bbox2[:4]

            x_overlap = max(0, min(x1_max, x2_max) - max(x1_min, x2_min))
            y_overlap = max(0, min(y1_max, y2_max) - max(y1_min, y2_min))
            intersection = x_overlap * y_overlap

            area1 = (x1_max - x1_min) * (y1_max - y1_min)
            if area1 == 0:
                return 0

            return intersection / area1

        def _point_in_bbox(x, y, bbox):
            """Bir noktanın bbox içinde olup olmadığını kontrol eder"""
            if not bbox or len(bbox) < 4:
                return False
            return bbox[0] <= x <= bbox[2] and bbox[1] <= y <= bbox[3]

        element_to_lines = {}

        if boxes and len(boxes) == len(lines):
            print(f"   🔍 {len(lines)} OCR satırı layout elementleriyle eşleştiriliyor...")

            for line_idx, (line_text, line_bbox) in enumerate(zip(lines, boxes)):
                if not line_bbox or len(line_bbox) < 4:
                    continue

                line_text_clean = line_text.strip()
                if not line_text_clean:
                    continue

                # Bu satırın merkez noktası
                line_center_x = (line_bbox[0] + line_bbox[2]) / 2
                line_center_y = (line_bbox[1] + line_bbox[3]) / 2

                # En iyi eşleşen layout elementini bul
                best_match = None
                best_score = 0

                for element in layout_elements:
                    element_bbox = element.get('bbox')
                    if not element_bbox or len(element_bbox) < 4:
                        continue

                    # Satır merkezi element içinde mi?
                    if _point_in_bbox(line_center_x, line_center_y, element_bbox):
                        # Overlap oranını hesapla
                        overlap = _calculate_overlap(line_bbox, element_bbox)

                        if overlap > best_score:
                            best_score = overlap
                            best_match = element

                if best_match and best_score > 0.1:
                    element_id = best_match['id']

                    if element_id not in element_to_lines:
                        element_to_lines[element_id] = []
                    element_to_lines[element_id].append((line_idx, line_text_clean))

        return element_to_lines

    def _create_ocr_sequence(self, element_to_lines, layout_elements):
        """
        Layout elementlerine göre OCR sequence oluştur.
        """
        ocr_sequence = []

        # ÖNCE TÜM ELEMENTLERI Y KOORDINATINA GÖRE SIRALA
        # Layout predictor'ın verdiği sırayı değil, gerçek pozisyonu kullan
        sorted_elements = sorted(layout_elements,
                                 key=lambda x: (x.get('bbox', [0, 0, 0, 0])[1], x.get('bbox', [0, 0, 0, 0])[0]))

        # Her elemente yeni reading order ver
        for reading_order, element in enumerate(sorted_elements, 1):
            element_id = element['id']

            if element_id not in element_to_lines:
                continue

            lines_in_element = element_to_lines[element_id]
            if not lines_in_element:
                continue

            sequence_info = {
                'element_id': element_id,
                'element_type': element.get('type', 'text'),
                'bbox': element.get('bbox'),
                'text_lines': lines_in_element,
                'reading_order': reading_order,  # Yeni hesaplanan sıra
                'confidence': element.get('confidence', 1.0)
            }
            ocr_sequence.append(sequence_info)
            # print(
            #     f"   🔢 Element {element_id} (bbox: {element.get('bbox', [0, 0, 0, 0])[:2]}) → Reading Order: {reading_order}")

        return ocr_sequence

    def _process_ocr_sequence(self, ocr_sequence):
        """
        OCR sequence'ını işleyerek sıralı paragraf yapısı oluştur.
        İyileştirmeler:
          - 1..9999 + Roma rakamı sayfa numarası filtresi
          - Kısa/uzun/soft/non-breaking tirelerle satır sonu birleştirme
          - Post-processing: yalnızca 'harf + (tire) + boşluk + küçük harf' (sol bitişik) birleştirme
          - Zero-width / soft hyphen temizliği
        """
        import re

        _HYPHENS = "\u002d\u00ad\u2010\u2011\u2012\u2013\u2014\u2015"  # - SHY ‐ - ‒ – — ―
        _LOWER_LETTERS = r"a-zçğıöşüà-žµß-öø-ÿ"

        def _strip_invisibles(s):
            if not s:
                return s
            return (s
                    .replace("\u00AD", "")  # soft hyphen
                    .replace("\u200B", "")  # ZWSP
                    .replace("\u200C", "")  # ZWNJ
                    .replace("\u200D", "")  # ZWJ
                    .replace("\u00A0", " ")  # NBSP
                    )

        def _is_page_number_advanced(txt):
            t = _strip_invisibles((txt or "")).strip()
            if not t:
                return False
            if t.isdigit() and 1 <= int(t) <= 9999:
                return True
            if re.match(r'^[IVXLCDMivxlcdm]+$', t):
                return True
            return False

        def _smart_merge_lines(lines):
            """
            Satır sonu hyphenation:
            - Satır sonu tire (+ Unicode varyantları) ve bir sonraki satır küçük harfle başlıyorsa birleştir.
            """
            if not lines:
                return lines

            result = []
            i = 0

            while i < len(lines):
                current_line = _strip_invisibles(lines[i]).strip()

                if not current_line:
                    i += 1
                    continue

                if i == len(lines) - 1:
                    result.append(current_line)
                    break

                next_line = _strip_invisibles(lines[i + 1]).strip() if i + 1 < len(lines) else ""

                if re.search(rf"[{_HYPHENS}]\s*$", current_line) and next_line:
                    if next_line[0].islower():
                        merged = re.sub(rf"[{_HYPHENS}]\s*$", "", current_line) + next_line
                        result.append(merged)
                        i += 2
                        continue

                result.append(current_line)
                i += 1

            return result

        def _fix_intraword_hyphen_splits(text):
            """
            Paragraf içi kelime-bölmesi düzeltmesi:
              [harf][tire][boşluk][küçük harf]  (sol bitişik şartı)
            'a - i' gibi anlamsal tireler korunur.
            """
            if not text:
                return text
            t = _strip_invisibles(text)
            pattern = re.compile(
                rf"([{_LOWER_LETTERS}])[{_HYPHENS}]\s+([{_LOWER_LETTERS}])",
                re.UNICODE
            )
            for _ in range(3):
                t_new = pattern.sub(r"\1\2", t)
                if t_new == t:
                    break
                t = t_new
            return t

        paragraphs = []

        # Sequence'ı element_id'ye göre sırala
        ocr_sequence.sort(key=lambda x: x['element_id'])

        for seq_item in ocr_sequence:
            element_type = (seq_item.get('element_type') or '')
            element_id = seq_item.get('element_id')

            # Satırları topla
            lines = []
            for pair in seq_item.get('text_lines', []):
                if isinstance(pair, (list, tuple)) and len(pair) >= 2:
                    _, line_text = pair[0], pair[1]
                else:
                    line_text = str(pair) if pair is not None else ""

                line_text = _strip_invisibles(line_text)
                if line_text and not _is_page_number_advanced(line_text):
                    lines.append(line_text)

            if lines:
                processed_lines = _smart_merge_lines(lines)
                full_text = ' '.join(s.strip() for s in processed_lines if s and s.strip())
                full_text = _fix_intraword_hyphen_splits(full_text)

                if not full_text:
                    continue

                is_heading = any(keyword in element_type.lower() for keyword in [
                    'title', 'heading', 'header', 'sectionheader', 'pageheader',
                    'başlık', 'baslik'
                ])

                if is_heading:
                    formatted_text = f"### {full_text}"
                    print(f"   BAŞLIK oluşturuldu: Element-{element_id}")
                else:
                    formatted_text = full_text
                    print(f"   TEXT oluşturuldu: Element-{element_id}")

                paragraphs.append(formatted_text)

        print(f"   ✅ Layout ile {len(paragraphs)} sıralı element oluşturuldu")
        return paragraphs

    def _post_process_merge_paragraphs(self, paragraphs):
        """
        Paragraf sonrası birleştirme işlemi - SectionHeader ve Markdown Heading (##, ###) satırlarını koruyarak.
        """
        if not paragraphs or len(paragraphs) < 2:
            return paragraphs

        print("   🔗 Paragraf birleştirme post-process başlıyor...")

        turkish_connectors = ['ve', 'veya', 'ile', 'da', 'de', 'ki']
        result = []
        i = 0

        while i < len(paragraphs):
            current_para = paragraphs[i]

            # SectionHeader veya Markdown Heading ise ASLA birleştirme, dokunma
            if (current_para.startswith('SectionHeader-') or
                    current_para.startswith('## ') or
                    current_para.startswith('### ')):
                result.append(current_para)
                i += 1
                continue

            # Son paragraf ise dokunma
            if i == len(paragraphs) - 1:
                result.append(current_para)
                i += 1
                continue

            next_para = paragraphs[i + 1]

            # Sonraki SectionHeader veya Markdown Heading ise mevcut paragrafı ekle ve devam et
            if (next_para.startswith('SectionHeader-') or
                    next_para.startswith('## ') or
                    next_para.startswith('### ')):
                result.append(current_para)
                i += 1
                continue

            # Sadece Text-X ile Text-Y'yi birleştir, SectionHeader veya Heading'lere dokunma
            should_merge = False
            merge_reason = ""

            current_trimmed = current_para.rstrip()
            if current_trimmed.endswith((',', '-')):
                should_merge = True
                merge_reason = "virgül/tire"
            elif not current_trimmed.endswith(('.', '!', '?')):
                next_words = next_para.strip().split()
                if next_words and next_words[0].lower() in turkish_connectors:
                    should_merge = True
                    merge_reason = f"bağlaç: {next_words[0]}"

            if should_merge:
                if current_trimmed.endswith(','):
                    merged = current_para + ' ' + next_para
                elif current_trimmed.endswith('-'):
                    merged = current_trimmed[:-1] + next_para
                else:
                    merged = current_para + ' ' + next_para

                result.append(merged)
                print(f"     ✅ Birleştirme: {merge_reason}")
                i += 2
            else:
                result.append(current_para)
                i += 1

        print(f"   🔗 Birleştirme tamamlandı: {len(paragraphs)} → {len(result)} paragraf")
        return result

    def group_lines_into_paragraphs(self, lines, boxes=None, layout_info=None):
        """
        OCR satırlarını layout analizi bilgisiyle birlikte paragraf yapısına gruplandırır.
        """
        import re

        if not lines:
            return []

        print(f"   🔧 Paragraf gruplama başlıyor...")
        print(f"       Satır sayısı: {len(lines)}")
        print(f"       Bbox bilgisi: {'Var' if boxes and len(boxes) == len(lines) else 'Yok'}")
        print(f"       Layout bilgisi: {'Var' if layout_info and len(layout_info) > 0 else 'Yok'}")

        # Layout analizi varsa ve kullanışlıysa öncelikle onu kullan
        if layout_info and len(layout_info) > 0:
            page_layout = layout_info[0]

            # Layout'ta anlamlı element var mı kontrol et
            total_elements = (len(page_layout.get('headings', [])) +
                              len(page_layout.get('paragraphs', [])) +
                              len(page_layout.get('text_blocks', [])))

            if total_elements > 0:
                print(f"   📋 Layout analizi kullanılıyor ({total_elements} element)")
                try:
                    result = self._group_with_layout_analysis(lines, boxes, layout_info)
                    if result and len(result) > 0:
                        print(f"   ✅ Layout analizi başarılı: {len(result)} paragraf")
                        # POST-PROCESSING: Paragraf birleştirme
                        final_result = self._post_process_merge_paragraphs(result)
                        return final_result
                    else:
                        print(f"   ⚠️ Layout analizi sonuçsuz, bbox analizine geçiliyor")
                except Exception as e:
                    print(f"   ❌ Layout analizi hata: {e}")
            else:
                print(f"   ⚠️ Layout boş elementler, bbox analizine geçiliyor")

        # Layout analizi yoksa veya başarısızsa gelişmiş bbox analizi kullan
        print(f"   🔍 Gelişmiş bbox analizi kullanılıyor...")

        def _is_page_number(txt):
            """Sayfa numarası tespiti"""
            t = txt.strip()
            if not t:
                return False

            # Sadece rakam (1-9999)
            if t.isdigit() and 1 <= int(t) <= 9999:
                return True

            # Roma rakamları
            if re.match(r'^[IVXLCDMivxlcdm]+$', t):
                return True

            # Tek karakter sayılar
            if len(t) == 1 and t.isdigit():
                return True

            return False

        def _is_definite_heading(txt, height=None, avg_height=None, is_first_line=False):
            """
            KONSERVATIF başlık tespiti - sadece kesin başlıkları yakalar
            """
            t = txt.strip()
            if not t or _is_page_number(t):
                return False

            # Çok uzun metinler başlık olamaz
            word_count = len(t.split())
            if word_count > 8:  # 8 kelimeden fazla başlık olamaz
                return False

            # Çok kısa metinler de başlık olamaz (sayfa numarası hariç)
            if len(t) < 3:
                return False

            # Font boyutu kontrolü - sadece BELIRGIN şekilde büyükse
            font_score = 0
            if height and avg_height:
                if height > avg_height * 1.5:  # %50 daha büyük olmalı
                    font_score = 2
                elif height > avg_height * 1.3:  # %30 daha büyük
                    font_score = 1

            # İçerik analizi - çok katı kriterler
            content_score = 0

            # Tamamen büyük harf (güçlü başlık işareti)
            if t.isupper() and word_count <= 6:
                content_score = 3

            # Özel başlık kalıpları (basit string kontrolü)
            if (t.startswith('BAB ') or
                    t.startswith('BÖLÜM ') or
                    t.startswith('FASIL') or
                    (len(t.split()) <= 3 and t.endswith('KIŞIM')) or
                    (len(t.split()) <= 3 and 'Kısım' in t)):
                content_score = 3

            # Toplam puan - sadece 4 ve üzeri başlık sayılır
            total_score = font_score + content_score

            # İlk satır bonus (eğer diğer kriterler de varsa)
            if is_first_line and total_score >= 2:
                total_score += 1

            return total_score >= 4

        def _is_word_breaking_hyphen(line1: str, line2: str, hyphen: str) -> bool:
            """
            Tirenin kelime bölme tiresi mi yoksa açıklama tiresi mi olduğunu belirler.
            
            Kelime bölme tiresi: satır sonunda kelimenin bölündüğü durum (kü-çük)
            Açıklama tiresi: "Bu konu - yani önemli olan - şudur" gibi kullanım
            """
            l1 = line1.strip()
            l2 = line2.strip()
            
            if not l1 or not l2:
                return False
            
            # Tire öncesi boşluk varsa -> açıklama tiresi, kelime bölme değil
            if len(l1) >= 2 and l1[-2] == ' ':
                return False
            
            # İkinci satır küçük harfle başlıyorsa -> kelime bölme olabilir
            if l2 and l2[0].islower():
                return True
            
            # Tire öncesinde harf varsa -> kelime bölme
            tire_oncesi = l1.rstrip(hyphen)
            if tire_oncesi and tire_oncesi[-1].isalpha():
                return True
            
            return False

        def _should_merge_lines(line1, line2):
            """
            İki satırın birleştirilip birleştirilmeyeceğini belirler.
            GELİŞTİRİLMİŞ TİRE KONTROLÜ ile
            """
            if not line1 or not line2:
                return False

            l1 = line1.strip()
            l2 = line2.strip()

            if not l1 or not l2:
                return False

            # 1. Virgül, noktalı virgül, iki nokta - kesin birleştir
            if l1.endswith((',', ';', ':')):
                return True

            # 2. Geliştirilmiş tire kontrolü
            hyphen_chars = ['-', '–', '—', '―', '‐', '‑']
            for hyphen in hyphen_chars:
                if l1.endswith(hyphen):
                    # Tire tipini analiz et
                    if _is_word_breaking_hyphen(l1, l2, hyphen):
                        return True
                    # Açıklama tiresi ise birleştirme (boşlukla)
                    return True

            # 3. Cümle sonu noktalama varsa birleştirme
            if l1.endswith(('.', '!', '?')):
                return False

            # 4. İkinci satır küçük harfle başlıyorsa - muhtemelen devam
            if l2[0].islower():
                return True

            # 5. Basit bağlaç kontrolü
            l1_words = l1.split()
            l2_words = l2.split()

            simple_connectors = ['ve', 'veya', 'ile', 'da', 'de', 'ki', 'ama', 'fakat', 'ancak', 'lakin']

            # İlk satır bağlaçla bitiyorsa devam eder
            if l1_words and l1_words[-1].lower() in simple_connectors:
                return True

            # İkinci satır bağlaçla başlıyorsa devam eder
            if l2_words and l2_words[0].lower() in simple_connectors:
                return True

            # 6. İlk satır çok kısa (3 kelimeden az) ve noktalama yok
            if len(l1_words) < 3 and not l1.endswith(('.', '!', '?')):
                return True

            return False

        def _merge_line_smart(current_lines, new_line):
            """Satırları akıllıca birleştirir"""
            if not current_lines:
                current_lines.append(new_line)
                return

            last_line = current_lines[-1]

            # Tire ile bitiyorsa kelimeyi kaynaştır
            if last_line.rstrip().endswith(('-', '–', '—', '―')):
                cleaned_last = last_line.rstrip('- –—―').rstrip()
                current_lines[-1] = cleaned_last + new_line.lstrip()
            else:
                # Normal boşlukla birleştir
                current_lines[-1] = last_line + ' ' + new_line

        # ANA İŞLEM AKIŞI
        paragraphs = []
        current_paragraph_lines = []

        # Bounding box bilgisi varsa kullan
        if boxes and len(boxes) == len(lines):
            print("   📏 Bbox bilgisi ile işleniyor...")

            # Bbox'ları y koordinatına göre sırala
            pairs = [(t, b) for t, b in zip(lines, boxes) if b and len(b) >= 4]
            if pairs:
                pairs.sort(key=lambda p: (p[1][1], p[1][0]))
                lines = [p[0] for p in pairs]
                boxes = [p[1] for p in pairs]

            heights = [max(1.0, bb[3] - bb[1]) for bb in boxes]
            avg_height = sum(heights) / len(heights) if heights else 18.0

            print(f"     Ortalama satır yüksekliği: {avg_height:.1f}")

            for i, (txt, bb) in enumerate(zip(lines, boxes)):
                text = (txt or "").strip()

                # Sayfa numarası atla
                if _is_page_number(text):
                    # Mevcut paragrafı bitir
                    if current_paragraph_lines:
                        combined = " ".join(current_paragraph_lines)
                        if combined.strip() and not _is_page_number(combined):
                            paragraphs.append(combined.strip())
                        current_paragraph_lines = []
                    continue

                # Boş satır atla
                if not text:
                    # Mevcut paragrafı bitir
                    if current_paragraph_lines:
                        combined = " ".join(current_paragraph_lines)
                        if combined.strip():
                            paragraphs.append(combined.strip())
                        current_paragraph_lines = []
                    continue

                line_height = heights[i]
                is_first = (i == 0)

                # Başlık kontrolü - KONSERVATIF
                is_heading = _is_definite_heading(text, line_height, avg_height, is_first)

                # Önceki satırla birleştirme kontrolü
                should_merge = False
                if current_paragraph_lines and not is_heading:
                    last_text = current_paragraph_lines[-1] if current_paragraph_lines else ""
                    should_merge = _should_merge_lines(last_text, text)

                # Yeni paragraf kararı
                if is_heading or (not should_merge and current_paragraph_lines):
                    # Mevcut paragrafı bitir
                    if current_paragraph_lines:
                        combined = " ".join(current_paragraph_lines)
                        if combined.strip():
                            paragraphs.append(combined.strip())
                        current_paragraph_lines = []

                    # Başlıkları özel işaretle
                    if is_heading:
                        paragraphs.append(f"## {text}")
                        print(f"     🏷️ Başlık tespit edildi: '{text[:30]}...'")
                    else:
                        current_paragraph_lines = [text]
                else:
                    # Mevcut paragrafa ekle
                    _merge_line_smart(current_paragraph_lines, text)

            # Son paragrafı ekle
            if current_paragraph_lines:
                combined = " ".join(current_paragraph_lines)
                if combined.strip():
                    paragraphs.append(combined.strip())

        else:
            print("   📝 Bbox olmadan işleniyor...")

            # Bbox bilgisi olmadan işle
            for i, raw_text in enumerate(lines):
                text = (raw_text or "").strip()

                # Sayfa numarası atla
                if _is_page_number(text):
                    if current_paragraph_lines:
                        combined = " ".join(current_paragraph_lines)
                        if combined.strip() and not _is_page_number(combined):
                            paragraphs.append(combined.strip())
                        current_paragraph_lines = []
                    continue

                # Boş satır atla
                if not text:
                    if current_paragraph_lines:
                        combined = " ".join(current_paragraph_lines)
                        if combined.strip():
                            paragraphs.append(combined.strip())
                        current_paragraph_lines = []
                    continue

                is_first = (i == 0)

                # Başlık kontrolü (bbox olmadan - daha da konservatif)
                is_heading = _is_definite_heading(text, is_first_line=is_first)

                # Birleştirme kontrolü
                should_merge = False
                if current_paragraph_lines and not is_heading:
                    last_text = current_paragraph_lines[-1] if current_paragraph_lines else ""
                    should_merge = _should_merge_lines(last_text, text)

                # Yeni paragraf kararı
                if is_heading or (not should_merge and current_paragraph_lines):
                    # Mevcut paragrafı bitir
                    if current_paragraph_lines:
                        combined = " ".join(current_paragraph_lines)
                        if combined.strip():
                            paragraphs.append(combined.strip())
                        current_paragraph_lines = []

                    if is_heading:
                        paragraphs.append(f"## {text}")
                        print(f"     🏷️ Başlık tespit edildi: '{text[:30]}...'")
                    else:
                        current_paragraph_lines = [text]
                else:
                    _merge_line_smart(current_paragraph_lines, text)

            # Son paragrafı ekle
            if current_paragraph_lines:
                combined = " ".join(current_paragraph_lines)
                if combined.strip():
                    paragraphs.append(combined.strip())

        # SON TEMİZLİK
        temp_result = []

        for paragraph in paragraphs:
            if paragraph and paragraph.strip():
                # HTML/XML etiketlerini temizle
                cleaned = re.sub(r'<[^>]+>', '', paragraph.strip())
                # Çoklu boşlukları temizle
                cleaned = re.sub(r'\s+', ' ', cleaned)

                if cleaned and len(cleaned) > 2 and not _is_page_number(cleaned):
                    temp_result.append(cleaned)

        # POST-PROCESSING: Paragraf birleştirme
        final_result = self._post_process_merge_paragraphs(temp_result)

        print(f"   ✅ Paragraf gruplama tamamlandı: {len(final_result)} paragraf")

        # Debug: İlk birkaç paragrafı göster
        for i, para in enumerate(final_result[:3]):
            para_type = "BAŞLIK" if para.startswith("## ") else "PARAGRAF"
            preview = para[:50] + "..." if len(para) > 50 else para
            print(f"     {i + 1}. {para_type}: '{preview}'")

        return final_result


    def _detect_page_number(self, page_layout, line_texts, line_boxes):
        """
        Layout bilgisi ve OCR satırlarından sayfa numarasını tespit eder.
        page_number_mapper.py mantığını kullanır.
        """
        if not page_layout:
            return None

        # Tüm layout elementlerini topla
        all_elements = (page_layout.get('headings', []) +
                        page_layout.get('paragraphs', []) +
                        page_layout.get('text_blocks', []))

        hf_bbox = None
        hf_label = None

        # PageHeader/PageFooter ara
        for element in all_elements:
            label = element.get('type', '').lower()
            if any(tag in label for tag in ['pagefooter', 'page-footer', 'footer', 'pageheader', 'page-header']):
                hf_bbox = element.get('bbox')
                hf_label = label
                break

        if not hf_bbox:
            return None

        try:
            return self._extract_page_number_logic(hf_bbox, line_texts, line_boxes)
        except Exception as e:
            print(f"⚠️ Sayfa no çıkarma hatası: {e}")
            return None

    def _extract_page_number_logic(self, hf_bbox, line_texts, line_boxes):
        """
        Bbox içindeki metni veya aynı Y-bandındaki metni bulur.
        """
        import re
        fx1, fy1, fx2, fy2 = hf_bbox
        footer_texts = []

        # 1. Bbox içinde metin ara
        for txt, bbox in zip(line_texts, line_boxes):
            if not bbox or len(bbox) < 4:
                continue

            lx1, ly1, lx2, ly2 = bbox
            # Y koordinatı toleransı
            if ly1 >= fy1 - 20 and ly2 <= fy2 + 20:
                # X koordinatı içinde mi?
                if lx2 >= fx1 and lx1 <= fx2:
                    if txt:
                        footer_texts.append(txt)

        all_text = " ".join(footer_texts)
        if all_text:
            numbers = re.findall(r'\b(\d{1,4})\b', all_text)
            if numbers:
                return int(numbers[0])

        # 2. Aynı Y-bandında ara
        return self._search_y_band_logic(fy1, fy2, line_texts, line_boxes)

    def _search_y_band_logic(self, fy1, fy2, line_texts, line_boxes):
        """
        Belirtilen Y aralığındaki (header/footer hizası) sayıları arar.
        """
        import re
        band_top = fy1 - 30
        band_bottom = fy2 + 30

        candidates = []
        for txt, bbox in zip(line_texts, line_boxes):
            if not bbox or len(bbox) < 4:
                continue

            lx1, ly1, lx2, ly2 = bbox
            if ly1 >= band_top and ly2 <= band_bottom:
                text = txt.strip()
                if not text:
                    continue
                
                # Sadece sayı veya kısa metin içindeki sayı
                numbers = re.findall(r'\b(\d{1,4})\b', text)
                if numbers and len(text) <= 10:
                    candidates.append((text, int(numbers[0])))

        if candidates:
            # En kısa metni seç (örn: "4" yerine "Sayfa 4" de olabilir ama "4" daha kesin)
            candidates.sort(key=lambda x: len(x[0]))
            return candidates[0][1]

        return None

    def perform_ocr(self, images, filename=None, actual_current_page=1, actual_total_pages=1):
        """
        RTX 5000 için Optimize edilmiş Batch OCR işlemi.
        """
        import re
        
        # Dinamik batch boyutu (GPU'ya göre ayarlanmış)
        BATCH_SIZE = getattr(self, 'optimal_batch_size', 12)
        use_amp = getattr(self, 'use_amp', False)
        amp_dtype = getattr(self, 'amp_dtype', torch.float32)
        
        print(f"📖 OCR başlıyor... (API: {SURYA_API}) - Toplam Görsel: {len(images)}")
        print(f"   Batch Size: {BATCH_SIZE}, AMP: {'Aktif' if use_amp else 'Pasif'}")

        results = []
        
        # --- 1. Layout Analizi ---
        layout_info_list = []
        if self.has_layout:
            try:
                if filename:
                    layout_start_progress = 20 + ((actual_current_page - 1) * 50 / actual_total_pages)
                    update_progress(filename, layout_start_progress + 2, f'Layout analizi yapılıyor...', actual_current_page, actual_total_pages)

                for i, image in enumerate(images):
                    try:
                        page_layout = self.analyze_layout(image, page_number=actual_current_page + i)
                        layout_info_list.append(page_layout)
                    except Exception as e:
                        print(f"   ⚠️ Layout hatası (Görsel {i}): {e}")
                        layout_info_list.append(None)
            except Exception as e:
                print(f"⚠️ Layout genel hatası: {e}")
                layout_info_list = [None] * len(images)
        else:
            layout_info_list = [None] * len(images)

        # --- 2. OCR İşlemi (BATCH PROCESSING) ---
        if SURYA_API == "new":
            if not self.has_recognition:
                raise RuntimeError("RecognitionPredictor yok")

            try:
                all_preds = []
                
                # Görselleri gruplara böl (Batching)
                for i in range(0, len(images), BATCH_SIZE):
                    batch_images = images[i : i + BATCH_SIZE]
                    batch_idx_start = actual_current_page + i
                    
                    if filename:
                        # Batch'deki ilk sayfa önizlemesi
                        batch_preview = None
                        try:
                            if batch_images:
                                preview_img = batch_images[0].copy()
                                preview_img.thumbnail((600, 800))
                                batch_preview = _create_base64_preview(preview_img)
                        except: pass
                        
                        ocr_prog = 20 + ((batch_idx_start - 1) * 50 / actual_total_pages) + 10
                        update_progress(filename, ocr_prog, f'OCR çalışıyor (Batch {i//BATCH_SIZE + 1})...', batch_idx_start, actual_total_pages, preview_image_url=batch_preview)

                    # ============================================
                    # RTX 5000 OPTİMİZASYONU: inference_mode + AMP
                    # ============================================
                    with torch.inference_mode():
                        batch_preds = self.recognizer(batch_images, det_predictor=self.detector)
                        all_preds.extend(batch_preds)
                    
                    print(f"⚡ Batch işlendi: {len(batch_images)} sayfa")
                    
                    # Bellek kontrolü
                    if torch.cuda.is_available():
                        mem_used_gb = torch.cuda.memory_allocated() / 1e9
                        mem_total_gb = self.gpu_info.get('memory_gb', 32)
                        if mem_used_gb > mem_total_gb * 0.85:
                            torch.cuda.empty_cache()
                            print(f"   🧹 Bellek temizlendi ({mem_used_gb:.1f}GB kullanımdaydı)")

                # --- 3. Sonuçları İşle ve Birleştir (BATCH İŞLEME DIŞI) ---
                for idx, pred in enumerate(all_preds):
                    current_abs_page = actual_current_page + idx
                    page_layout = layout_info_list[idx] if idx < len(layout_info_list) else None

                    # --- Satırları Çıkar ---
                    line_texts, line_boxes, line_confidences = [], [], []

                    if hasattr(pred, "text_lines") and pred.text_lines:
                        for line in pred.text_lines:
                            txt = getattr(line, 'text', str(line)).strip()
                            conf = getattr(line, 'confidence', 0.95)
                            try: conf = float(conf)
                            except: conf = 0.95
                            
                            box = None
                            if hasattr(line, "bbox"):
                                try: box = list(line.bbox) if not hasattr(line.bbox, "tolist") else line.bbox.tolist()
                                except: box = None
                            
                            if txt:
                                line_texts.append(txt)
                                line_boxes.append(box)
                                line_confidences.append(conf)
                    
                    elif hasattr(pred, "text") and pred.text:
                        text_content = pred.text
                        lines = text_content.split('\n') if isinstance(text_content, str) else text_content
                        for t in lines:
                            st = str(t).strip()
                            if st: line_texts.append(st); line_boxes.append(None); line_confidences.append(0.95)

                    # --- Paragraf Gruplama ---
                    grouped_paragraphs = self.group_lines_into_paragraphs(
                        line_texts, line_boxes, [page_layout] if page_layout else None
                    )

                    # --- Formatlama ---
                    paragraphs = []
                    paragraph_counter = 0
                    for paragraph_text in grouped_paragraphs:
                        if paragraph_text:
                            cleaned_text = self.clean_ocr_output(paragraph_text)
                            if not cleaned_text: continue
                            paragraph_counter += 1

                            is_heading = False
                            text_content = cleaned_text
                            para_type = "paragraph"

                            heading_match = re.match(r'^(#{2,})\s*(.*)', cleaned_text, re.DOTALL)
                            if heading_match:
                                is_heading = True
                                para_type = "heading"
                                text_content = self.clean_ocr_output(heading_match.group(2))
                            
                            confidence = 0.98 if is_heading else (
                                sum(line_confidences) / len(line_confidences) if line_confidences else 0.95)

                            if not text_content: continue

                            paragraphs.append({
                                "paragraph_number": paragraph_counter,
                                "text": text_content,
                                "type": para_type,
                                "confidence": confidence
                            })


                    full_text = "\n".join(
                        f"\n{p['text'].upper()}\n" if p["type"] == "heading" else p["text"]
                        for p in paragraphs
                    ).strip()

                    # --- Sayfa Numarası Tespiti (Layout + OCR ile) ---
                    detected_pn = self._detect_page_number(page_layout, line_texts, line_boxes)
                    
                    is_detected = False
                    final_page_number = current_abs_page
                    if detected_pn:
                        final_page_number = detected_pn
                        is_detected = True
                        print(f"   🔖 Sayfa No Tespit Edildi: {detected_pn} (PDF Sayfası: {current_abs_page})")

                    results.append({
                        "page_number": final_page_number,      # Eserin (yazılan) sayfa numarası
                        "pdf_page_number": current_abs_page,   # PDF'teki fiziksel sıra
                        "is_page_number_detected": is_detected,
                        "paragraphs": paragraphs,
                        "full_text": full_text,
                        "layout_info": page_layout
                    })

                    if filename:
                        page_end_progress = 20 + (current_abs_page * 50 / actual_total_pages)
                        update_progress(filename, page_end_progress, f'Sayfa {current_abs_page} tamamlandı', current_abs_page, actual_total_pages)

                # --- 4. Ardışık Sayfa Numarası Düzeltme ---
                # NOT: Post-processing artık process_file'da tüm sayfalar toplandıktan sonra yapılıyor
                pass

            except Exception as e:
                print(f"❌ Batch OCR Hatası: {e}")
                return self._ocr_with_detection_only(images, filename=filename, actual_current_page=actual_current_page, actual_total_pages=actual_total_pages)

        elif SURYA_API == "old":
            print("⚠️ Eski API - layout analizi desteklenmiyor")
            try:
                if filename:
                    ocr_start_progress = 20 + ((actual_current_page - 1) * 50 / actual_total_pages) + 10
                    update_progress(filename, ocr_start_progress,
                                    f'Sayfa {actual_current_page} OCR başlatılıyor (eski API)...', actual_current_page,
                                    actual_total_pages)

                ocr = run_ocr(images, self.supported_languages)

                for page_idx, page in enumerate(ocr):
                    current_page = actual_current_page

                    line_texts, line_confidences = [], []
                    for item in page.get("text_lines", []):
                        txt = (item.get("text", "") or "").strip()
                        conf = item.get("confidence", 0.95)
                        if txt: line_texts.append(txt); line_confidences.append(conf)

                    grouped_paragraphs = self.group_lines_into_paragraphs(line_texts, boxes=None, layout_info=None)

                    paragraphs = []
                    paragraph_counter = 0
                    for paragraph_text in grouped_paragraphs:
                        if paragraph_text:
                            cleaned_text = self.clean_ocr_output(paragraph_text)
                            if not cleaned_text: continue
                            paragraph_counter += 1

                            is_heading = False
                            text_content = cleaned_text
                            para_type = "paragraph"

                            heading_match = re.match(r'^(#{2,})\s*(.*)', cleaned_text, re.DOTALL)

                            if heading_match:
                                is_heading = True
                                para_type = "heading"
                                text_content = self.clean_ocr_output(heading_match.group(2))
                            else:
                                text_content = cleaned_text

                            confidence = 0.98 if is_heading else (
                                sum(line_confidences) / len(line_confidences) if line_confidences else 0.95)

                            if not text_content:
                                continue

                            paragraphs.append({
                                "paragraph_number": paragraph_counter,
                                "text": text_content,
                                "type": para_type,
                                "confidence": confidence
                            })

                    full_text = "\n".join(
                        f"\n{p['text'].upper()}\n" if p["type"] == "heading" else p["text"]
                        for p in paragraphs
                    ).strip()

                    page_result = {
                        "page_number": current_page,
                        "paragraphs": paragraphs,
                        "full_text": full_text
                    }
                    results.append(page_result)

                    if filename:
                        page_end_progress = 20 + (actual_current_page * 50 / actual_total_pages)
                        update_progress(filename, page_end_progress, f'Sayfa {current_page} OCR tamamlandı (eski API)',
                                        current_page, actual_total_pages)

            except Exception as e:
                print(f"❌ Eski API OCR hatası: {e}")
                import traceback
                print(traceback.format_exc())
                raise

        print(f"✅ OCR tamamlandı: {len(results)} sayfa işlendi")
        return results

    def get_processing_stats_for_ui(self, ocr_results):
        """
        OCR sonuçlarından UI için gerçek istatistikleri hesaplar
        """
        total_chars = 0
        total_headings = 0
        total_blocks = 0

        try:
            for page in ocr_results:
                paragraphs = page.get('paragraphs', [])
                for paragraph in paragraphs:
                    text = paragraph.get('text', '')
                    para_type = paragraph.get('type', 'paragraph')

                    # Karakter sayısı
                    total_chars += len(text)

                    # Başlık sayısı
                    if para_type == 'heading':
                        total_headings += 1

                    # Toplam blok (her paragraf bir blok)
                    total_blocks += 1

            return {
                'charactersProcessed': total_chars,
                'headingsFound': total_headings,
                'blocksDetected': total_blocks
            }
        except Exception as e:
            print(f"⚠️ İstatistik hesaplama hatası: {e}")
            return {
                'charactersProcessed': 0,
                'headingsFound': 0,
                'blocksDetected': 0
            }


    def _apply_sequential_page_number_correction(self, results):
        """
        page_number_mapper.py mantığında ardışık sayfa numaralarını düzeltir ve boşlukları doldurur.
        Result listesi üzerinde çalışır.
        """
        if not results:
            return results

        n = len(results)
        # Sadece tespit edilenleri al, edilemeyenleri None yap (gap filling için)
        values = []
        for res in results:
            if res.get('is_page_number_detected'):
                try:
                    values.append(int(res.get('page_number')))
                except:
                    values.append(None)
            else:
                values.append(None)

        # FAZ 1: OCR Hatalarını Düzelt
        ocr_fixes = 0
        for i in range(1, n - 1):
            if values[i] is None:
                continue

            # Önceki tespiti bul
            prev_val, prev_dist = None, 0
            for j in range(i - 1, -1, -1):
                prev_dist += 1
                if values[j] is not None:
                    prev_val = values[j]
                    break

            # Sonraki tespiti bul
            next_val, next_dist = None, 0
            for j in range(i + 1, n):
                next_dist += 1
                if values[j] is not None:
                    next_val = values[j]
                    break

            if prev_val is None or next_val is None:
                continue

            # Beklenen değerler
            expected_from_prev = prev_val + prev_dist
            expected_from_next = next_val - next_dist
            
            current = values[i]
            # Eğer değer hatalıysa (hem prev hem next ile tutarsız) ama prev ve next kendi aralarında tutarlıysa
            if current != expected_from_prev and current != expected_from_next:
                if next_val - prev_val == prev_dist + next_dist:
                    # Tutarlı bir dizi var, ama mevcut değer yanlış
                    corrected = expected_from_prev
                    print(f"   🔧 OCR Düzeltme (PDF s.{results[i]['pdf_page_number']}): {current} -> {corrected}")
                    values[i] = corrected
                    results[i]['page_number'] = corrected
                    # results[i]['is_page_number_detected'] = True # Düzeltildi
                    ocr_fixes += 1

        if ocr_fixes > 0:
            print(f"   ✅ {ocr_fixes} OCR sayfa numarası hatası düzeltildi")

        # FAZ 2: Boşlukları Doldur (Gap Filling)
        i = 0
        fills = 0
        while i < n:
            if values[i] is not None:
                i += 1
                continue

            gap_start = i
            while i < n and values[i] is None:
                i += 1
            gap_end = i
            gap_size = gap_end - gap_start

            # Önceki ve sonraki değerleri al
            prev_val = values[gap_start - 1] if gap_start > 0 else None
            next_val = values[gap_end] if gap_end < n else None

            # --- BAŞLANGIÇTAKİ BOŞLUĞU DOLDURMA (Geriye Doğru Tahmin) ---
            if gap_start == 0 and prev_val is None and next_val is not None:
                # Geriye doğru sayarak 1. sayfanın ne olması gerektiğini bul
                implied_start_page = next_val - gap_size
                
                # Eğer 1. sayfa < 1 çıkıyorsa (örn: 0 veya -1), bu demektir ki
                # tespit edilen sıralama (next_val) kitabın/dosyanın başıyla uyumsuz.
                # Bu durumda 1'den başlayarak doldur.
                if implied_start_page <= 0:
                     print(f"   ⚠️ Başlangıç boşluğu uyuşmazlığı: Tespit edilen {next_val}, 1. sayfanın {implied_start_page} olmasını gerektiriyor.")
                     print("   🔄 Sıralama 1'den başlayacak şekilde düzeltiliyor (Fiziksel Sıra Önceliği)")
                     
                     for k in range(gap_start, gap_end):
                         val = k + 1 
                         values[k] = val
                         results[k]['page_number'] = val
                         fills += 1
                     
                     # Çakışma kontrolü: Eğer doldurduğumuz son değer, bir sonraki tespit edilen değere eşit veya büyükse
                     last_filled = gap_end # values[gap_end-1]
                     if last_filled >= next_val:
                         print(f"   ⚠️ Çakışma düzeltildi: Tespit edilen {next_val} -> {last_filled + 1} olarak güncellendi.")
                         values[gap_end] = last_filled + 1
                         results[gap_end]['page_number'] = last_filled + 1
                         # values dizisini güncelledik, sonraki iterasyonlarda bu yeni değeri kullanacağız.
                
                else:
                    # Geriye doğru sayım mantıklı (1 veya daha büyük)
                    # O zaman normal geriye doldurma yapalım
                     for k in range(gap_start, gap_end):
                         val = implied_start_page + k
                         values[k] = val
                         results[k]['page_number'] = val
                         fills += 1
                     print(f"   🔗 Geriye Doğru Doldurma (Start Page {implied_start_page}): PDF s.{gap_start+1}-{gap_end}")

            if prev_val is not None and next_val is not None:
                actual_diff = next_val - prev_val
                expected_diff = gap_size + 1
                
                if actual_diff == expected_diff:
                    # Ardışık doldur
                    for k in range(gap_start, gap_end):
                        val = prev_val + (k - gap_start + 1)
                        values[k] = val
                        results[k]['page_number'] = val
                        fills += 1
                    print(f"   🔗 Boşluk Dolduruldu: PDF s.{gap_start+1}-{gap_end}")
            
            i = gap_end

        if fills > 0:
            print(f"   ✅ {fills} sayfa numarası boşluğu dolduruldu")

        return results

    def _ocr_with_detection_only(self, images: List[Image.Image]) -> List[Dict]:
        """Sadece detection ile basit OCR simülasyonu"""
        print("🔄 Detection-only modunda çalışıyor...")

        try:
            detection_results = self.detect_text_regions(images)

            processed_results = []

            for page_data in detection_results:
                ocr_page = {
                    'page_number': page_data['page_number'],
                    'paragraphs': [],
                    'full_text': ''
                }

                # Her tespit edilen bölge için simüle metin
                for i, region in enumerate(page_data['text_regions']):
                    paragraph_info = {
                        'paragraph_number': i + 1,
                        'text': f"[Tespit edilen metin bölgesi {i + 1} - Recognition modeli gerekli]",
                        'confidence': region['confidence']
                    }
                    ocr_page['paragraphs'].append(paragraph_info)

                ocr_page['full_text'] = '\n\n'.join([p['text'] for p in ocr_page['paragraphs']])
                processed_results.append(ocr_page)

            return processed_results

        except Exception as e:
            print(f"❌ Detection-only OCR hatası: {e}")
            raise

    def generate_markdown_output(self, ocr_results: List[Dict], filename: str) -> str:
        """
        Markdown formatında çıktı oluşturur.
        """
        try:
            # Calculate average confidence
            total_confidence = 0.0
            paragraph_count = 0

            for page in ocr_results:
                for paragraph in page.get('paragraphs', []):
                    total_confidence += paragraph.get('confidence', 0.0)
                    paragraph_count += 1

            avg_confidence = total_confidence / paragraph_count if paragraph_count > 0 else 0.0

            # Update metadata with processing info
            if self.metadata_manager.has_metadata():
                self.metadata_manager.update_processing_info(
                    page_count=len(ocr_results),
                    confidence=avg_confidence,
                    source_filename=filename,
                    source_format=Path(filename).suffix.lower()
                )

            # Generate basic content
            if self.metadata_manager.has_metadata():
                # Start with metadata header instead of simple title
                content = ""
            else:
                # Fallback to original simple header
                content = f"# {filename.upper()}\n\n"
                content += f"*{datetime.now().strftime('%d.%m.%Y %H:%M')}*\n\n"

            for page in ocr_results:
                page_num = page.get('page_number', '?')
                pdf_page_num = page.get('pdf_page_number', '?')
                
                header_text = f"## Sayfa {page_num}"
                if str(page_num) != str(pdf_page_num):
                    header_text += f" - PDF Sayfası {pdf_page_num}"
                
                content += f"{header_text}\n\n"

                if page['paragraphs']:
                    for paragraph in page['paragraphs']:
                        paragraph_type = paragraph.get('type', 'paragraph')
                        para_text = self.clean_ocr_output(paragraph.get('text', ''))
                        
                        # Paragraf numarasını al (Yoksa '?' koy)
                        para_num = paragraph.get('paragraph_number', '?')
                        
                        # STANDART ETİKET: "** Paragraf [X]**" ve hemen ardından yeni satır (\n)
                        # Bu sayede alttaki Markdown (başlık vs.) bozulmaz.
                        label_line = f"**Paragraf [{para_num}]**\n"

                        if not para_text:
                            continue

                        # --- TİP KONTROLÜ VE FORMATLAMA ---
                        
                        if paragraph_type == 'heading':
                            # Başlık (#) işareti satır başında olmalı, bu yüzden label_line'dan sonra ekliyoruz
                            heading_text = para_text.lstrip('#').strip()
                            content += f"{label_line}### {heading_text}\n\n"
                            
                        elif paragraph_type == 'title':
                            title_text = para_text.lstrip('#').strip()
                            content += f"{label_line}## {title_text}\n\n"
                            
                        elif paragraph_type == 'sectionheader':
                            section_text = para_text.lstrip('#').strip()
                            content += f"{label_line}### {section_text}\n\n"
                            
                        elif paragraph_type == 'pageheader':
                            header_text = para_text.lstrip('#').strip()
                            content += f"{label_line}*{header_text}*\n\n"
                            
                        elif paragraph_type == 'footnote':
                            content += f"{label_line}> {para_text}\n\n"
                            
                        elif paragraph_type == 'footer':
                            content += f"{label_line}*{para_text}*\n\n"
                            
                        elif paragraph_type == 'listitem':
                            # Liste elemanları için de etiketi üste koyuyoruz
                            # Not: Liste işareti yoksa ekliyoruz
                            clean_item = para_text.strip()
                            if clean_item.startswith(('-', '*', '+', '•')) or \
                               re.match(r'^\d+[\.\)]\s+', clean_item):
                                content += f"{label_line}{clean_item}\n\n"
                            else:
                                content += f"{label_line}- {clean_item}\n\n"
                                
                        elif paragraph_type == 'caption':
                            content += f"{label_line}*{para_text}*\n\n"
                            
                        else:
                            # Normal paragraf
                            content += f"{label_line}{para_text}\n\n"

            # Footer
            content += "---\n\n"
            content += f"**Toplam Sayfa:** {len(ocr_results)}\n"
            content += f"**İşlem Tarihi:** {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"

            # Apply metadata enhancement if available
            if self.metadata_manager.has_metadata():
                enhanced_content = self.metadata_manager.generate_enhanced_markdown(content, filename)
                return enhanced_content

            return content

        except Exception as e:
            print(f"❌ Markdown oluşturma hatası: {e}")
            raise

    def _decode_xml_entities_in_text_nodes(self, xml_string: str) -> str:
        """
        XML çıktısındaki metin düğümlerinde bulunan entity'leri gerçek karakterlere çevirir.
        Öznitelik değerlerindeki entity'ler korunur (XML yapısını bozmamak için).

        Örnek:
            <paragraf>&quot;Merhaba&quot; &lt;dünya&gt;</paragraf>
            ↓
            <paragraf>"Merhaba" <dünya></paragraf>

        NOT: Bu işlem sadece metin düğümlerinde yapılır, tag ve özniteliklere dokunulmaz.
        """
        import re

        def decode_text_content(match):
            """Tag içindeki metin kısmını decode eder."""
            opening_tag = match.group(1)
            text_content = match.group(2)
            closing_tag = match.group(3)

            decoded_text = text_content
            entity_map = {
                '&quot;': '"',
                '&apos;': "'",
                '&lt;': '<',
                '&gt;': '>',
            }

            for entity, char in entity_map.items():
                decoded_text = decoded_text.replace(entity, char)

            # &amp; en son yapılmalı
            decoded_text = decoded_text.replace('&amp;', '&')

            return f"{opening_tag}{decoded_text}{closing_tag}"

        # Metin içeren tag'leri bul ve decode et
        pattern = r'(<(?:paragraf|sayfa|e|metadata_value|title|author|description|keywords|category|language|source_filename|source_format|processed_date|processor_version|page_count|average_confidence)[^>]*>)([^<]+)(</(?:paragraf|sayfa|e|metadata_value|title|author|description|keywords|category|language|source_filename|source_format|processed_date|processor_version|page_count|average_confidence)>)'

        result = re.sub(pattern, decode_text_content, xml_string)

        return result

    def generate_xml_output(self, ocr_results: List[Dict], filename: str) -> str:
        """ XML formatında çıktı oluşturur. NLP uyumluluğu için özel karakter temizliği içerir. """
        import re
        import xml.etree.ElementTree as ET
        from datetime import datetime
        import html
        from pathlib import Path

        # --- Yardımcılar (lokal) ---
        def _make_valid_xml_tag(name: str) -> str:
            """Dosya adından güvenli bir kök etiket adı üretir."""
            base = str(name or "").split('/')[-1]
            base = re.sub(r'[^\w\-_.]', '_', base)
            base = re.sub(r'_{2,}', '_', base).strip('_')
            if not base:
                base = "document"
            if not re.match(r'^[A-Za-z_]', base):
                base = "doc_" + base
            if re.match(r'^(?i:xml)', base):
                base = "doc_" + base
            return base

        def _clean_for_nlp_strict(text: str) -> str:
            """
            NLP süreçleri için kritik temizlik.
            Yasaklı karakterler: < > { } & ( )
            Bu karakterleri boşluk ile değiştirir ve fazla boşlukları temizler.
            """
            if text is None:
                return ""
            s = str(text)
            
            # 1. Yasaklı karakterleri boşlukla değiştir (Kelimelerin yapışmaması için)
            # Regex: <, >, {, }, &, (, )
            s = re.sub(r'[<>{}\&()]', ' ', s)
            
            # 2. XML 1.0 için geçersiz kontrol karakterlerini temizle
            illegal = re.compile(u'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x84\x86-\x9f]')
            s = illegal.sub('', s)
            
            # 3. Fazla boşlukları tekile indir
            s = re.sub(r'\s+', ' ', s).strip()
            
            return s

        def _escape_attr_value(v) -> str:
            """Attribute değerleri için temizlik."""
            if v is None:
                return ""
            # Attribute'larda da aynı temizliği uyguluyoruz
            clean_val = _clean_for_nlp_strict(str(v))
            return html.escape(clean_val, quote=True)

        def _detect_paragraph_type(text: str, para_dict: dict) -> str:
            """Paragraf tipini tespit eder."""
            existing_type = para_dict.get('type', '').lower().strip()
            layout_types = ['heading', 'title', 'sectionheader', 'pageheader',
                            'footnote', 'footer', 'caption', 'listitem', 'list',
                            'paragraph']

            if existing_type in layout_types:
                return existing_type

            text_stripped = text.strip()
            if text_stripped.startswith('###'): return 'heading'
            elif text_stripped.startswith('##'): return 'heading'
            elif text_stripped.startswith('#'): return 'title'

            text_clean = text_stripped.lstrip('#').strip()
            if re.match(r'^\d+[\.\)]\s+', text_clean) or text_clean.startswith('*'):
                return 'footnote'
            if re.match(r'^[\-\*\+•]\s+', text_clean) or re.match(r'^\d+[\.\)]\s+', text_clean):
                return 'listitem'

            return 'paragraph'

        try:
            # Ortalama güven hesabı
            total_confidence = 0.0
            paragraph_count = 0
            for page in ocr_results:
                for paragraph in page.get('paragraphs', []):
                    total_confidence += float(paragraph.get('confidence', 0.0) or 0.0)
                    paragraph_count += 1
            avg_confidence = (total_confidence / paragraph_count) if paragraph_count > 0 else 0.0

            # Kök etiket adı
            root_tag = _make_valid_xml_tag(filename)

            # Metadata güncelleme
            if hasattr(self, 'metadata_manager') and self.metadata_manager.has_metadata():
                self.metadata_manager.update_processing_info(
                    page_count=len(ocr_results),
                    confidence=avg_confidence,
                    source_filename=filename,
                    source_format=Path(filename).suffix.lower()
                )

            # ----- METHOD 1: ElementTree ile Temiz XML Üretimi -----
            try:
                root = ET.Element(root_tag)
                root.set('processed_date', datetime.now().isoformat())
                root.set('processor', 'SuryaOCR_Pro')
                
                esc_source = _clean_for_nlp_strict(filename)
                if esc_source:
                    root.set('source_file', esc_source)

                # Sayfalar döngüsü
                for page in ocr_results:
                    page_el = ET.SubElement(root, 'sayfa')
                    page_el.set('number', str(page.get('page_number', '')))
                    # PDF sayfasını ekle
                    pdf_pg = str(page.get('pdf_page_number', ''))
                    if pdf_pg and pdf_pg != str(page.get('page_number', '')):
                         page_el.set('pdf_sayfasi', pdf_pg)
                    
                    page_el.set('paragraph_count', str(len(page.get('paragraphs', []))))

                    for paragraph in page.get('paragraphs', []):
                        para_el = ET.SubElement(page_el, 'paragraf')
                        para_el.set('number', str(paragraph.get('paragraph_number', '')))

                        raw_text = str(paragraph.get('text', '')).strip()
                        # Genel temizlik
                        cleaned_text = self.clean_ocr_output(raw_text)
                        
                        # Tip tespiti
                        detected_type = _detect_paragraph_type(cleaned_text, paragraph)
                        para_el.set('type', detected_type)

                        # Markdown işaretlerini temizle (Metin içeriği için)
                        if detected_type in ['heading', 'title']:
                            cleaned_text = re.sub(r'^#{1,6}\s*', '', cleaned_text).strip()

                        # NLP İÇİN KRİTİK TEMİZLİK: < > { } & ( )
                        final_nlp_text = _clean_for_nlp_strict(cleaned_text)

                        # Text node'a ata
                        para_el.text = final_nlp_text

                # XML string üretimi
                xml_body = ET.tostring(root, encoding='unicode', method='xml')
                final_xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_body

                # Metadata varsa (Metadata XML'inin de temizlenmesi gerekebilir, ancak
                # şimdilik ana yapıyı koruyoruz. Metadata yöneticisi ayrı çalışıyor.)
                if hasattr(self, 'metadata_manager') and self.metadata_manager.has_metadata():
                    try:
                        enhanced_xml = self.metadata_manager.generate_enhanced_xml(final_xml, filename)
                        # Metadata eklendikten sonra tekrar genel bir temizlik riskli olabilir (tagleri bozabilir).
                        # Bu yüzden metadata yöneticisinin çıktısına güveniyoruz veya 
                        # en son text node temizliği yapıyoruz.
                        return self._decode_xml_entities_in_text_nodes(enhanced_xml)
                    except Exception as me:
                        print(f"⚠️ Metadata enhancement failed (devam ediliyor): {me}")

                return self._decode_xml_entities_in_text_nodes(final_xml)

            except Exception as e1:
                print(f"⚠️ ElementTree yolunda hata: {e1}")
                # Fallback yöntemine geçiş

            # ----- METHOD 2: MANUEL FALLBACK (NLP Temizliği ile) -----
            print("🔧 Using fallback XML generation for NLP.")
            xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>']

            root_attrs = [
                f'processed_date="{html.escape(datetime.now().isoformat())}"',
                'processor="SuryaOCR_Pro"'
            ]
            
            clean_filename = _clean_for_nlp_strict(filename)
            if clean_filename:
                root_attrs.append(f'source_file="{html.escape(clean_filename, quote=True)}"')

            xml_lines.append(f'<{root_tag} {" ".join(root_attrs)}>')

            for page in ocr_results:
                page_num = page.get('page_number', '')
                pdf_num = page.get('pdf_page_number', '')
                para_count = len(page.get('paragraphs', []))
                
                page_attr = f'number="{page_num}"'
                if pdf_num and str(pdf_num) != str(page_num):
                    page_attr += f' pdf_sayfasi="{pdf_num}"'
                page_attr += f' paragraph_count="{para_count}"'

                xml_lines.append(f'  <sayfa {page_attr}>')

                for paragraph in page.get('paragraphs', []):
                    para_num = paragraph.get('paragraph_number', '')
                    para_text = str(paragraph.get('text', '')).strip()

                    detected_type = _detect_paragraph_type(para_text, paragraph)

                    if detected_type in ['heading', 'title']:
                        para_text = re.sub(r'^#{1,6}\s*', '', para_text).strip()

                    # NLP Temizliği
                    nlp_safe_text = _clean_for_nlp_strict(para_text)
                    # XML için escape (artık & ve < > olmadığı için html.escape daha az iş yapacak ama güvenli)
                    escaped_text = html.escape(nlp_safe_text, quote=False)

                    xml_lines.append(
                        f'    <paragraf number="{para_num}" type="{detected_type}">')
                    xml_lines.append(f'      {escaped_text}')
                    xml_lines.append('    </paragraf>')

                xml_lines.append('  </sayfa>')

            xml_lines.append(f'</{root_tag}>')
            final_xml = '\n'.join(xml_lines)

            return final_xml

        except Exception as e:
            print(f"❌ XML oluşturma hatası: {e}")
            import traceback
            print(f"🔍 Traceback: {traceback.format_exc()}")
            safe_name = _make_valid_xml_tag(filename)
            return f'''<?xml version="1.0" encoding="UTF-8"?>
        <{safe_name} processed_date="{html.escape(datetime.now().isoformat())}">
        <error>XML generation failed: {html.escape(str(e))}</error>
        </{safe_name}>'''

    def clean_ocr_output(self, text: str) -> str:
        """
        OCR çıktısını profesyonelce temizler:
        1. HTML entity'lerini (örn: &quot;, &lt;) gerçek karakterlere çevirir.
        2. <br>, </p> gibi yapısal tagleri yeni satıra (\n) dönüştürür.
        3. <math> içeriğini koruyarak taglerini siler.
        4. Geriye kalan TÜM HTML/XML taglerini tek seferde siler.
        5. LaTeX ve gereksiz boşlukları temizler.
        """
        import re
        import html

        if not text or not isinstance(text, str):
            return ""

        # 1. HTML Entity'lerini Çöz (Döngüsel - iç içe geçmişler için)
        # Örn: &lt;br&gt; -> <br> haline gelir.
        curr_text = text
        for _ in range(3):
            decoded = html.unescape(curr_text)
            if decoded == curr_text:
                break
            curr_text = decoded
        text = curr_text

        # 2. Yapısal Tagleri Yeni Satıra Çevir
        # <br> etiketlerini yeni satır yap (metinler yapışmasın)
        text = re.sub(r'<\s*br\s*/?>', '\n', text, flags=re.IGNORECASE)
        # Paragraf/Div bitişlerini yeni satır yap
        text = re.sub(r'</(p|div|tr|li|h\d)>', '\n', text, flags=re.IGNORECASE)

        # 3. Math Taglerini İşle (İçeriği koru, sarmalayan tagi sil)
        text = re.sub(r'<math[^>]*>(.*?)</math>', r'\1', text, flags=re.DOTALL | re.IGNORECASE)

        # 4. Kalan TÜM HTML Taglerini Sil (Genel Süpürme)
        # <...> şeklindeki her şeyi siler. Tek tek replace yapmaya gerek kalmaz.
        text = re.sub(r'<[^>]+>', '', text)

        # 5. LaTeX Temizlikleri (Mevcut koddan korunanlar)
        text = re.sub(r'\\mathbf\{([^}]*)\}', r'\1', text)
        text = re.sub(r'\\mathcal\{([^}]*)\}', r'\1', text)
        text = re.sub(r'\\sqrt\{([^}]*)\}', r'√\1', text)
        text = re.sub(r'\\overline\{([^}]*)\}', r'\1', text)

        # Karmaşık LaTeX ifadeleri
        text = re.sub(r'\{[A-Z]\}\^\{\}_?\{\{[^}]+\}\}', '', text)
        text = re.sub(r'\{[^}]{0,3}\}\^\{[^}]*\}', '', text)

        # LaTeX operatörleri
        text = text.replace(r'\cdot', '·')
        text = text.replace(r'\sim', '~')
        text = text.replace(r'\rho', 'ρ')
        text = text.replace(r'\theta', 'θ')
        text = text.replace(r'\omega', 'ω')
        text = re.sub(r'\\[a-zA-Z]+', '', text)

        # 5b. Emoji ve Gereksiz Unicode Sembol Temizliği
        # Tarihi metinlerde OCR'ın halüsinasyon olarak ürettiği emoji/sembol karakterleri siler.
        # Türkçe harfler, standart noktalama ve matematiksel semboller korunur.
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # Emoticons (😀-🙏)
            "\U0001F300-\U0001F5FF"  # Misc Symbols & Pictographs (🌀-🗿)
            "\U0001F680-\U0001F6FF"  # Transport & Map Symbols (🚀-🛿)
            "\U0001F1E0-\U0001F1FF"  # Flags (🇦-🇿)
            "\U0001F900-\U0001F9FF"  # Supplemental Symbols (🤀-🧿)
            "\U0001FA00-\U0001FA6F"  # Chess symbols etc.
            "\U0001FA70-\U0001FAFF"  # Symbols Extended-A
            "\U00002702-\U000027B0"  # Dingbats (✂-➰)
            "\U000024C2-\U0001F251"  # Enclosed chars & misc
            "\U0000FE00-\U0000FE0F"  # Variation Selectors
            "\U0000200D"             # Zero Width Joiner
            "\U00002640-\U00002642"  # Gender symbols
            "\U00002600-\U000026FF"  # Misc Symbols (☀-⛿)
            "\U00002700-\U000027BF"  # Dingbats
            "\U0000231A-\U0000231B"  # Watch, Hourglass
            "\U000023E9-\U000023F3"  # Media control
            "\U000023F8-\U000023FA"  # Media control cont.
            "\U0000200B"             # Zero Width Space
            "\U0000FEFF"             # BOM
            "\U0000FFFC-\U0000FFFD"  # Object replacement, replacement char
            "]+",
            flags=re.UNICODE
        )
        text = emoji_pattern.sub('', text)

        # 6. Gürültü Filtreleme
        noise_phrases = [
            r'\bmanufacture\s+file\b',
            r'\baccording\s+to\b',
            r'\bfile\s+number\b',
            r'\bdocument\s+id\b',
        ]
        for pattern in noise_phrases:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)

        text = re.sub(r'\b\d{4,}\s+[A-Z]{1,3}\b', '', text)
        text = re.sub(r'(\b\w\b\s+){3,}', lambda m: m.group(0).replace(' ', ''), text)

        # 7. Boşluk Düzenleme
        # Çoklu yeni satırları ve boşlukları tekile indir
        text = re.sub(r'\n\s*\n', '\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        text = text.strip()

        # 8. Son Kontrol (Kısa/Anlamsız metin filtresi)
        if len(text) < 10:
            return text

        latin_chars = len(re.findall(r'[a-zA-ZçğıöşüÇĞİÖŞÜ]', text))
        total_chars = len(re.sub(r'\s', '', text))

        if total_chars > 0 and latin_chars / total_chars < 0.3:
            if len(text) > 50:
                return text
            else:
                return ""

        return text

    def generate_enhanced_xml(self,
                              original_xml: str,
                              filename: str = "") -> str:
        """Generate XML with metadata section - COMPLETELY REWRITTEN"""
        if not self.has_metadata():
            return original_xml

        # Update filename if provided
        if filename and not self.current_metadata.source_filename:
            self.current_metadata.source_filename = filename

        try:
            print(f"🔍 Debugging XML enhancement...")
            print(f"   Original XML length: {len(original_xml)}")
            print(f"   Original XML starts with: {repr(original_xml[:50])}")

            # Clean the input XML
            cleaned_xml = original_xml.strip()

            # Remove any problematic characters at the start
            while cleaned_xml and cleaned_xml[
                0] in '\ufeff\ufffe\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f':
                cleaned_xml = cleaned_xml[1:]

            print(f"   Cleaned XML starts with: {repr(cleaned_xml[:50])}")

            # Find the actual XML content (skip XML declaration)
            xml_content = cleaned_xml
            if cleaned_xml.startswith('<?xml'):
                declaration_end = cleaned_xml.find('?>') + 2
                xml_content = cleaned_xml[declaration_end:].strip()

            print(f"   XML content starts with: {repr(xml_content[:50])}")

            # Ensure we have valid XML content
            if not xml_content or not xml_content.startswith('<'):
                print(f"⚠️ Invalid XML content, returning original")
                return original_xml

            # Parse the XML content
            try:
                root = ET.fromstring(xml_content)
                print(f"✅ Successfully parsed XML, root tag: {root.tag}")
            except ET.ParseError as e:
                print(f"⚠️ Parse error: {e}")
                print(f"   Trying with encoding fix...")

                # Try encoding fixes
                try:
                    # Try UTF-8 encoding
                    encoded_content = xml_content.encode('utf-8')
                    parser = ET.XMLParser(encoding='utf-8')
                    root = ET.fromstring(encoded_content, parser=parser)
                    print(f"✅ Parsed with UTF-8 encoding")
                except Exception as e2:
                    print(f"⚠️ UTF-8 encoding failed: {e2}")
                    return original_xml

            # Add metadata to the parsed root
            self.current_metadata.generate_xml_metadata(root)

            # Convert back to string
            enhanced_xml_content = ET.tostring(root, encoding='unicode', method='xml')

            # Add XML declaration back
            final_xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + enhanced_xml_content

            # Pretty format manually (safer than minidom)
            try:
                lines = []
                current_indent = 0
                indent_step = "  "

                # Split into lines and add proper indentation
                for line in final_xml.split('\n'):
                    stripped = line.strip()
                    if not stripped:
                        continue

                    if stripped.startswith('<?xml'):
                        lines.append(stripped)
                    elif stripped.startswith('</'):
                        current_indent = max(0, current_indent - 1)
                        lines.append(indent_step * current_indent + stripped)
                    elif stripped.endswith('/>'):
                        lines.append(indent_step * current_indent + stripped)
                    elif '<' in stripped and '>' in stripped:
                        lines.append(indent_step * current_indent + stripped)
                        if not stripped.endswith('>') or '></' not in stripped:
                            current_indent += 1
                    else:
                        lines.append(indent_step * current_indent + stripped)

                pretty_xml = '\n'.join(lines)

                # Validate the final result
                try:
                    ET.fromstring(pretty_xml.split('\n', 1)[1])  # Skip XML declaration for validation
                    print("✅ Enhanced XML is valid")
                    return pretty_xml
                except ET.ParseError as e:
                    print(f"⚠️ Enhanced XML validation failed: {e}")
                    return final_xml  # Return without pretty formatting

            except Exception as pretty_error:
                print(f"⚠️ Pretty formatting failed: {pretty_error}")
                return final_xml

        except Exception as e:
            print(f"⚠️ XML metadata enhancement failed: {e}")
            import traceback
            print(f"🔍 Full traceback: {traceback.format_exc()}")
            return original_xml

    def set_document_metadata(self, metadata: DocumentMetadata) -> None:
        """Set metadata for current document processing"""
        self.metadata_manager.set_metadata(metadata)

    def clear_document_metadata(self) -> None:
        """Clear current document metadata"""
        self.metadata_manager.clear_metadata()

    def get_metadata_json(self) -> str:
        """Get current metadata as JSON"""
        return self.metadata_manager.export_metadata_json()

    def process_file(self, file_path: str, process_mode: str = 'ocr', output_formats: List[str] = None,
                     progress_key: str = None, user_metadata_dict: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Ana dosya işleme fonksiyonu - İlerleme takibi ile.
        MODIFIED: perform_ocr ve _process_newspaper_ocr çağrılarına doğru parametreleri iletir.
        VE EK OLARAK: İşlem sonrası staging dosyasını temizler.
        """
        import traceback
        import time
        from pathlib import Path

        print(f"📖 İşlem başlıyor... (Dosya: {Path(file_path).name}, Mod: {process_mode})")

        # GPU bilgi
        if torch.cuda.is_available():
            print(f"🎯 Başlangıç - GPU bellek: {torch.cuda.memory_allocated() / 1e6:.1f}MB, Cache: {torch.cuda.memory_reserved() / 1e6:.1f}MB")

        # Metadata logic
        user_metadata = {}
        if user_metadata_dict:
            # If provided directly, use it to update manager
            try:
                metadata_obj = create_metadata_from_form(user_metadata_dict)
                self.set_document_metadata(metadata_obj)
                user_metadata = user_metadata_dict
                print(f"📝 Metadata request'ten alındı: {user_metadata.get('title', 'Başlıksız')}")
            except Exception as e:
                print(f"⚠️ Metadata oluşturma hatası: {e}")
                user_metadata = {}
        else:
            # Fallback to current manager state
            try:
                meta_json = self.metadata_manager.export_metadata_json()
                user_metadata = json.loads(meta_json) if meta_json else {}
                print("📝 Metadata manager'dan alındı")
            except Exception as e:
                print(f"⚠️ Metadata okuma hatası: {e}")
                user_metadata = {}

        key_for_updates = progress_key if progress_key else Path(file_path).name
        print(f"🔑 İlerleme Anahtarı: {key_for_updates}")

        # Staging dosyası temizleme için path
        p = Path(file_path)

        try:
            # Çıktı formatlarını normalize et
            allowed = ['md', 'xml']
            norm = []
            if isinstance(output_formats, list):
                for x in output_formats:
                    items_to_check = x if isinstance(x, (list, tuple)) else [x]
                    for item in items_to_check:
                        if isinstance(item, str):
                            norm.append(item.strip().lower())
            elif isinstance(output_formats, str):
                norm = [output_formats.strip().lower()]

            output_formats = [fmt for fmt in allowed if fmt in norm]
            if not output_formats: output_formats = ['md']

            print(f"📜 İstenen Çıktı Formatları: {output_formats}")

            if not p.exists():
                raise FileNotFoundError(f"Dosya bulunamadı: {file_path}")
            filename = p.name

            current_document_id = None
            current_job_id = None

            # Veritabanı entegrasyonu
            if DATABASE_INTEGRATION_AVAILABLE and is_database_integration_enabled():
                try:
                    existing_results = check_for_existing_results(str(p), user_metadata)
                    if existing_results and existing_results.get('success'):
                        print(f"🎯 Cache'den sonuç bulundu: {filename}")
                        update_progress(key_for_updates, 100, 'Cache\'den yüklendi!', 1, 1)
                        cleanup_progress_after_delay(key_for_updates, 5)
                        return existing_results

                    print(f"💾 Yeni işlem veritabanına kaydediliyor...")
                    processing_ids = register_new_processing(
                        str(p), process_mode, output_formats, metadata=user_metadata
                    )
                    if processing_ids:
                        current_document_id, current_job_id = processing_ids
                        try:
                            self.set_current_processing_ids(current_document_id, current_job_id)
                        except AttributeError:
                            pass
                        print(f"📋 İşlem kaydedildi - Doc: {current_document_id}, Job: {current_job_id}")
                except Exception as db_error:
                    print(f"⚠️ Veritabanı hatası (işleme devam ediliyor): {db_error}")

            # Sonuç yapısı
            update_progress(key_for_updates, 0, 'İşlem başlatılıyor...', 0, 0)
            result: Dict[str, Any] = {
                'success': False, 'filename': filename, 'file_path': str(p),
                'process_mode': process_mode, 'page_count': 0,
                'processing_time': 0.0, 'outputs': {},
            }
            t0 = time.time()

            # Dosya yükleme
            update_progress(key_for_updates, 5, 'Dosya yükleniyor...', 0, 0)
            from PIL import Image
            Image.MAX_IMAGE_PIXELS = None

            images: List[Image.Image] = []
            file_extension = p.suffix.lower()

            if file_extension == '.pdf':
                update_progress(key_for_updates, 10, 'PDF sayfaları ayrılıyor...', 0, 0)
                images = self.pdf_to_images(str(p))
            elif file_extension in ['.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp', '.webp']:
                update_progress(key_for_updates, 10, 'Görsel işleniyor...', 0, 0)
                try:
                    image = Image.open(str(p))
                    max_dimension = 8000
                    if image.width > max_dimension or image.height > max_dimension:
                        ratio = min(max_dimension / image.width, max_dimension / image.height)
                        new_size = (int(image.width * ratio), int(image.height * ratio))
                        print(f"⚠️ Büyük görsel -> yeniden boyutlandırılıyor: {new_size}")
                        image = image.resize(new_size, Image.Resampling.LANCZOS)
                    if image.mode not in ['RGB', 'L']: image = image.convert('RGB')
                    images = [image]
                except Exception as img_error:
                    raise ValueError(f"Görsel yüklenemedi: {img_error}")
            else:
                raise ValueError(f"Desteklenmeyen dosya formatı: {file_extension}")

            if not images:
                raise ValueError("Dosyadan görüntü alınamadı.")

            total_pages = len(images)
            result['page_count'] = total_pages
            
            # İlk sayfa önizlemesi oluştur
            first_page_preview = None
            if images:
                try:
                    # Orijinal görüntüyü thumbnail yap
                    preview_img = images[0].copy()
                    preview_img.thumbnail((600, 800))
                    first_page_preview = _create_base64_preview(preview_img)
                except: pass
            
            update_progress(key_for_updates, 15, f'Dosya yüklendi: {total_pages} sayfa', 0, total_pages, preview_image_url=first_page_preview)

            # --- İşleme Modu ---
            if process_mode == 'detection':
                update_progress(key_for_updates, 20, 'Metin bölgeleri tespiti...', 0, total_pages)
                detection_results = []
                for page_idx, image in enumerate(images):
                    current_page = page_idx + 1
                    progress = 20 + (page_idx * 60 / total_pages)
                    update_progress(key_for_updates, progress, f'Sayfa {current_page} tespit ediliyor...', current_page, total_pages)
                    try:
                        page_detection = self.detect_text_regions([image])
                        if page_detection: detection_results.extend(page_detection)
                    except Exception as det_err:
                        detection_results.append({
                            'page_number': current_page,
                            'text_regions': [], 'region_count': 0,
                            'error': str(det_err)
                        })

                result['detection_results'] = detection_results
                result['success'] = True

            elif process_mode == 'ocr':
                update_progress(key_for_updates, 20, 'OCR işlemi başlatılıyor...', 0, total_pages)

                is_newspaper = False
                if self.gazete_processor:
                    update_progress(key_for_updates, 18, 'Doküman tipi analizi...', 0, total_pages)
                    try:
                        is_newspaper = self.gazete_processor.is_newspaper(images, threshold=3)
                        result['document_type'] = 'newspaper' if is_newspaper else 'standard'
                    except:
                        result['document_type'] = 'standard'

                if is_newspaper and self.gazete_processor:
                    ocr_results = self._process_newspaper_ocr(images, key_for_updates, total_pages)
                else:
                    ocr_results = []
                    for page_idx, image in enumerate(images):
                        current_page = page_idx + 1
                        base_progress = 20 + (page_idx * 50 / total_pages)
                        update_progress(key_for_updates, base_progress, f'Sayfa {current_page} işleniyor...',
                                        current_page, total_pages)
                        try:
                            page_result_list = self.perform_ocr(
                                [image],
                                filename=key_for_updates,
                                actual_current_page=current_page,
                                actual_total_pages=total_pages
                            )
                            if page_result_list: ocr_results.extend(page_result_list)
                        except Exception as page_err:
                            ocr_results.append({'page_number': current_page, 'paragraphs': [],
                                                'full_text': f'[Sayfa işlenemedi: {page_err}]',
                                                'error': str(page_err)})


                # --- Ardışık Sayfa Numarası Düzeltme (TÜM sayfalar toplandıktan sonra) ---
                try:
                    ocr_results = self._apply_sequential_page_number_correction(ocr_results)
                    print(f'✅ Ardışık sayfa numarası düzeltme tamamlandı ({len(ocr_results)} sayfa)')
                except Exception as post_err:
                    print(f'⚠️ Ardışık sayfa düzeltme hatası: {post_err}')

                result['ocr_results'] = ocr_results

                update_progress(key_for_updates, 75, 'Çıktı formatları hazırlanıyor...', total_pages, total_pages)

                if 'md' in output_formats:
                    try:
                        md_text = self.generate_markdown_output(ocr_results, filename)
                        result['outputs']['md'] = md_text
                    except Exception as e:
                        result['outputs']['md_error'] = str(e)

                if 'xml' in output_formats:
                    try:
                        xml_text = self.generate_xml_output(ocr_results, filename)
                        result['outputs']['xml'] = xml_text
                    except Exception as e:
                        result['outputs']['xml_error'] = str(e)

                result['success'] = True

            else:
                raise ValueError(f"Desteklenmeyen işlem modu: {process_mode}")

            # -------------------------------
            # 🔥 STAGING DOSYASI TEMİZLİĞİ EKLENDİ
            # -------------------------------
            try:
                images.clear()     # Windows lock sorunlarını önler
                if p.exists():
                    import os
                    os.remove(p)
                    print(f"🧹 Staging dosyası temizlendi: {p.name}")
                else:
                    print(f"ℹ️ Staging dosyası zaten yok: {p.name}")
            except Exception as cleanup_error:
                print(f"⚠️ Staging dosyası silinemedi (önemsiz): {cleanup_error}")
            # -------------------------------

            result['processing_time'] = float(time.time() - t0)
            update_progress(key_for_updates, 100, 'İşlem tamamlandı!', total_pages, total_pages)
            cleanup_progress_after_delay(key_for_updates, 10)

            # DB finalize
            if (DATABASE_INTEGRATION_AVAILABLE and is_database_integration_enabled() and
                current_document_id and current_job_id):
                try:
                    finalize_processing(current_document_id, current_job_id, result)
                except:
                    pass
                finally:
                    try:
                        self.clear_current_processing_ids()
                    except AttributeError:
                        pass

            return result

        except Exception as e:
            error_message = f"{type(e).__name__}: {e}"
            print(f"❌ Ana İşlem Hatası: {error_message}")

            update_progress(key_for_updates, -1, f"Hata: {error_message}", 0, 0, error=True)
            cleanup_progress_after_delay(key_for_updates, 10)

            # DB hata finalize
            if (DATABASE_INTEGRATION_AVAILABLE and is_database_integration_enabled() and
                current_document_id and current_job_id):
                try:
                    error_result = {**result, 'success': False, 'error': error_message}
                    finalize_processing(current_document_id, current_job_id, error_result)
                except:
                    pass
                finally:
                    try:
                        self.clear_current_processing_ids()
                    except AttributeError:
                        pass

            return {'success': False, 'error': error_message}


    def _clean_newspaper_text(self, text: str) -> str:
        """
        Gazete metinleri için özel temizlik.
        Tire ile bölünmüş kelimeleri birleştirir.
        """
        import re

        if not text or not isinstance(text, str):
            return ""

        # Önce standart temizlik
        text = self.clean_ocr_output(text)

        if not text:
            return ""

        # --- TIRE BIRLESTIRME ---
        # Türkçe ve Latin harfleri
        letters = r'a-zA-ZçğıöşüÇĞİÖŞÜâîûêôÂÎÛÊÔ'

        # Tire karakterleri (tüm varyantlar)
        hyphens = r'\-\u2010\u2011\u2012\u2013\u2014\u00AD'

        # Pattern 1: "kelime- devam" -> "kelimedevam"
        # Satır sonunda tire + boşluk + küçük harf ile devam
        pattern1 = re.compile(
            rf'([{letters}])[{hyphens}]\s+([a-zçğıöşü])',
            re.UNICODE
        )

        # Pattern 2: "kelime -devam" -> "kelimedevam" (tire başta)
        pattern2 = re.compile(
            rf'([{letters}])\s+[{hyphens}]([a-zçğıöşü])',
            re.UNICODE
        )

        # Pattern 3: "kelime - devam" -> "kelimedevam" (tire ortada boşluklu)
        # Sadece küçük harfle başlıyorsa (büyük harfse yeni cümle olabilir)
        pattern3 = re.compile(
            rf'([{letters}])\s+[{hyphens}]\s+([a-zçğıöşü])',
            re.UNICODE
        )

        # Birden fazla geçiş yap (iç içe durumlar için)
        for _ in range(5):
            original = text
            text = pattern1.sub(r'\1\2', text)
            text = pattern2.sub(r'\1\2', text)
            text = pattern3.sub(r'\1\2', text)
            if text == original:
                break

        # --- EK TEMIZLIKLER ---

        # Soft hyphen ve zero-width karakterleri temizle
        text = text.replace('\u00AD', '')  # Soft hyphen
        text = text.replace('\u200B', '')  # Zero-width space
        text = text.replace('\u200C', '')  # Zero-width non-joiner
        text = text.replace('\u200D', '')  # Zero-width joiner
        text = text.replace('\uFEFF', '')  # BOM

        # Çoklu boşlukları tek boşluğa indir
        text = re.sub(r'\s+', ' ', text)

        # Başta/sonda boşluk temizle
        text = text.strip()

        return text

    def _process_newspaper_ocr(self, images: List[Image.Image], filename: str, total_pages: int) -> List[Dict]:
        """
        Gazete için özel OCR işleme.
        RTX 5000 Ada için optimize edilmiştir (Yüksek VRAM eşiği).
        """
        import gc

        print(f"📰 Gazete OCR işleme başlıyor... ({total_pages} sayfa)")

        ocr_results = []
        consecutive_failures = 0
        max_consecutive_failures = 3

        for page_idx, image in enumerate(images):
            current_page = page_idx + 1
            actual_current_page = current_page
            actual_total_pages = total_pages

            base_progress = 20 + (page_idx * 50 / actual_total_pages)

            # Sayfa önizlemesi
            page_preview = None
            try:
                preview_img = image.copy()
                preview_img.thumbnail((600, 800))
                page_preview = _create_base64_preview(preview_img)
            except: pass

            update_progress(filename, base_progress,
                            f'📰 Sayfa {actual_current_page} - Gazete layout analizi...',
                            actual_current_page, actual_total_pages, preview_image_url=page_preview)

            # --- GPU BELLEK YONETIMI (RTX 5000 Ada Optimized) ---
            try:
                if torch.cuda.is_available():
                    # Sadece bellek durumunu oku, hemen temizleme yapma
                    memory_allocated = torch.cuda.memory_allocated() / (1024 ** 3)
                    
                    # EŞİK DEĞİŞTİRİLDİ: 32GB kart için 24GB'a kadar izin ver.
                    # Gereksiz boşaltmalar performansı düşürür.
                    if memory_allocated > 24.0:
                        print(f"⚠️ Sayfa {actual_current_page}: Yüksek VRAM ({memory_allocated:.2f}GB), temizlik yapılıyor...")
                        gc.collect()
                        torch.cuda.empty_cache()
            except Exception as mem_error:
                print(f"⚠️ Bellek kontrol hatası: {mem_error}")

            try:
                # Gazete processor ile sayfayı işle
                gazete_result = self.gazete_processor.process_gazete_page(image)
                consecutive_failures = 0

                # Sonucu standart formata çevir
                page_result = {
                    'page_number': actual_current_page,
                    'paragraphs': [],
                    'full_text': '',
                    'document_type': 'newspaper',
                    'statistics': gazete_result.get('statistics', {})
                }

                # Paragrafları dönüştür ve temizle
                paragraph_counter = 0
                for para in gazete_result.get('paragraphs', []):
                    cleaned_text = self._clean_newspaper_text(para.get('text', ''))
                    if not cleaned_text: continue
                    paragraph_counter += 1
                    
                    page_result['paragraphs'].append({
                        'paragraph_number': para.get('number', paragraph_counter),
                        'text': cleaned_text,
                        'type': para.get('type', 'paragraph'),
                        'confidence': para.get('confidence', 0.95)
                    })

                # Tam metin oluştur
                full_text_parts = []
                for p in page_result['paragraphs']:
                    if p['type'] == 'heading':
                        full_text_parts.append(f"\n{p['text'].upper()}\n")
                    else:
                        full_text_parts.append(p['text'])
                page_result['full_text'] = "\n".join(full_text_parts).strip()

                ocr_results.append(page_result)

                # Sayfa sonu ilerleme güncellemesi
                page_progress = 20 + ((page_idx + 1) * 50 / actual_total_pages)
                update_progress(filename, page_progress,
                                f'📰 Sayfa {actual_current_page} tamamlandı',
                                actual_current_page, actual_total_pages)

            except RuntimeError as cuda_error:
                error_str = str(cuda_error)
                if "out of memory" in error_str.lower() or "CUDA" in error_str:
                    consecutive_failures += 1
                    print(f"⚠️ Sayfa {actual_current_page} CUDA OOM hatası. Temizleniyor...")
                    
                    # OOM durumunda tam temizlik
                    gc.collect()
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                        torch.cuda.synchronize()

                    ocr_results.append({
                        'page_number': actual_current_page,
                        'paragraphs': [],
                        'full_text': '[GPU bellek yetersizliği nedeniyle atlandı]',
                        'error': 'CUDA out of memory',
                        'document_type': 'newspaper'
                    })

                    if consecutive_failures >= max_consecutive_failures:
                        print("❌ Çok fazla ardışık hata, işlem durduruluyor.")
                        break
                else:
                    print(f"⚠️ Hata: {cuda_error}")
                    ocr_results.append({'page_number': actual_current_page, 'paragraphs': [], 'full_text': str(cuda_error), 'error': str(cuda_error)})

            except Exception as page_error:
                print(f"⚠️ Genel Hata: {page_error}")
                ocr_results.append({'page_number': actual_current_page, 'paragraphs': [], 'full_text': str(page_error), 'error': str(page_error)})

        print(f"✅ Gazete OCR tamamlandı: {len(ocr_results)} sayfa")
        return ocr_results

    def visualize_layout(self, image, layout_info, method='surya'):
        """
        Layout sonuçlarını görsel olarak işaretle

        Args:
            image: PIL Image
            layout_info: Layout analiz sonucu (dict veya LayoutResult)
            method: 'surya' veya 'yolo'
        """
        import io
        import base64

        # Görüntü üzerine çizim yap
        img_copy = image.copy()
        draw = ImageDraw.Draw(img_copy)

        # Renk paleti - her tip için farklı renk
        colors = {
            'title': '#FF6B6B',
            'heading': '#4ECDC4',
            'paragraph': '#45B7D1',
            'text': '#96CEB4',
            'list': '#FFEAA7',
            'table': '#DFE6E9',
            'figure': '#A29BFE',
            'caption': '#FD79A8',
            'sectionheader': '#74B9FF',
            'pageheader': '#A29BFE',
            'footer': '#DFE6E9'
        }

        visualizations = []

        if method == 'surya':
            # ✅ layout_info artık dict formatında (analyze_layout'tan geliyor)
            if isinstance(layout_info, dict):
                all_elements = (layout_info.get('headings', []) +
                                layout_info.get('paragraphs', []) +
                                layout_info.get('text_blocks', []))

                print(f"   🎨 Surya: {len(all_elements)} element çizilecek")

                for element in all_elements:
                    try:
                        bbox = element.get('bbox', [])
                        if not bbox or len(bbox) < 4:
                            continue

                        element_type = element.get('type', 'text')
                        confidence = element.get('confidence', 1.0)
                        element_id = element.get('id', 0)

                        # Renk seç
                        color = colors.get(element_type, '#95A5A6')
                        rgb_color = tuple(int(color.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4))

                        # Dikdörtgen çiz
                        draw.rectangle(bbox, outline=rgb_color, width=3)

                        # Label text
                        text = f"{element_type.upper()} #{element_id} ({confidence * 100:.1f}%)"

                        try:
                            font = ImageFont.truetype("arial.ttf", 14)
                        except:
                            font = ImageFont.load_default()

                        # Text arka planı
                        text_bbox = draw.textbbox((bbox[0], bbox[1] - 20), text, font=font)
                        draw.rectangle(text_bbox, fill=rgb_color)
                        draw.text((bbox[0], bbox[1] - 20), text, fill='white', font=font)

                        visualizations.append({
                            'id': element_id,
                            'type': element_type,
                            'bbox': bbox,
                            'confidence': confidence
                        })

                    except Exception as e:
                        print(f"     ⚠️ Element çizim hatası: {e}")
                        continue

        elif method == 'yolo' and self.gazete_processor:
            # YOLO layout sonuçlarını görselleştir
            if hasattr(layout_info, 'boxes'):
                boxes = layout_info.boxes
                print(f"   🎨 YOLO: {len(boxes)} element çizilecek")

                for i in range(len(boxes)):
                    try:
                        box = boxes.xyxy[i].cpu().numpy()
                        conf = float(boxes.conf[i].cpu().numpy())
                        cls = int(boxes.cls[i].cpu().numpy())

                        # YOLO class names
                        class_names = self.gazete_processor.yolo_model.names
                        label = class_names.get(cls, 'unknown')

                        color = colors.get(label, '#95A5A6')
                        rgb_color = tuple(int(color.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4))

                        # Dikdörtgen çiz
                        draw.rectangle(box.tolist(), outline=rgb_color, width=3)

                        # Label text
                        text = f"{label.upper()} ({conf * 100:.1f}%)"

                        try:
                            font = ImageFont.truetype("arial.ttf", 14)
                        except:
                            font = ImageFont.load_default()

                        text_bbox = draw.textbbox((box[0], box[1] - 20), text, font=font)
                        draw.rectangle(text_bbox, fill=rgb_color)
                        draw.text((box[0], box[1] - 20), text, fill='white', font=font)

                        visualizations.append({
                            'id': i + 1,
                            'type': label,
                            'bbox': box.tolist(),
                            'confidence': conf
                        })

                    except Exception as e:
                        print(f"     ⚠️ YOLO visualize error: {e}")
                        continue

        # Image'i base64'e çevir
        buffered = io.BytesIO()
        img_copy.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode()

        print(f"   ✅ Görselleştirme tamamlandı: {len(visualizations)} element")

        return {
            'image': f"data:image/png;base64,{img_base64}",
            'detections': visualizations,
            'method': method
        }

    def get_layout_comparison(self, image):
        """
        Hem Surya hem YOLO layout tespiti yap ve karşılaştır
        """
        results = {
            'surya': None,
            'yolo': None
        }

        # Surya layout
        if self.has_layout:
            try:
                print("🔍 Surya layout analizi yapılıyor...")

                # analyze_layout kullan
                surya_layout_dict = self.analyze_layout(image, page_number=1)

                if surya_layout_dict:
                    # Görselleştir
                    results['surya'] = self.visualize_layout(image, surya_layout_dict, 'surya')
                    print(f"✅ Surya visualize tamamlandı")
                else:
                    print(f"⚠️ Surya layout sonucu boş")

            except Exception as e:
                print(f"❌ Surya layout hatası: {e}")
                import traceback
                print(traceback.format_exc())

        # YOLO layout
        if self.gazete_processor and self.gazete_processor.yolo_available:
            try:
                print("🔍 YOLO layout analizi yapılıyor...")

                yolo_result = self.gazete_processor.yolo_model(image)[0]
                results['yolo'] = self.visualize_layout(image, yolo_result, 'yolo')

                print(f"✅ YOLO visualize tamamlandı")

            except Exception as e:
                print(f"❌ YOLO layout hatası: {e}")
                import traceback
                print(traceback.format_exc())

        return results

    def set_current_processing_ids(self, document_id: str, job_id: str):
        """Set current processing IDs for database tracking"""
        global current_document_id, current_job_id
        current_document_id = document_id
        current_job_id = job_id

    def get_current_processing_ids(self) -> tuple:
        """Get current processing IDs"""
        global current_document_id, current_job_id
        return (current_document_id, current_job_id)

    def clear_current_processing_ids(self):
        """Clear current processing IDs"""
        global current_document_id, current_job_id
        current_document_id = None
        current_job_id = None


# Using api_bp imported from . at the top of the file

# Global processor instance
processor = None
processing_status = {}

current_document_id = None
current_job_id = None
progress_queues = {}


def _create_base64_preview(img: Image.Image, format="JPEG", quality=75) -> str:
    """Bir PIL Görüntüsünü Base64 Data URI'ye dönüştürür."""
    try:
        buffered = io.BytesIO()
        img_format = format.upper()

        # Görüntüyü RGB'ye dönüştür (eğer RGBA, P vb. ise)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")

        if img_format == "JPEG":
            img.save(buffered, format="JPEG", quality=quality, optimize=True)
        else:
            img_format = "PNG"  # Varsayılan
            img.save(buffered, format="PNG", optimize=True)

        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        return f"data:image/{img_format.lower()};base64,{img_str}"
    except Exception as e:
        print(f"Base64 oluşturma hatası: {e}")
        return None


def init_processor():
    """Processor'ı başlat"""
    global processor
    try:
        if processor is not None:
            print("ℹ️  Processor is already initialized.")
            return True
            
        print("🚀 Processor initialization starting...")
        processor = SuryaProcessor()

        # Database integration initialize
        if DATABASE_INTEGRATION_AVAILABLE:
            try:
                initialize_processing_integration()
            except Exception as e:
                print(f"⚠️ Database entegrasyonu başlatılamadı: {e}")

        print("✅ Processor initialized successfully!")
        return True
    except Exception as e:
        print(f"❌ Processor başlatma hatası: {e}")
        import traceback
        print(traceback.format_exc())
        return False


# Automatically start processor initialization in a background thread
# This prevents the Flask app from blocking during startup but models will be ready as fast as possible.
print("📡 Background processor initialization thread starting...")
threading.Thread(target=init_processor, daemon=True).start()


def cleanup_progress_after_delay(filename, delay=10):
    """Clean up progress info after delay"""
    if not filename:
        return

    def cleanup():
        time.sleep(delay)
        if filename in processing_status:
            processing_status.pop(filename, None)
            print(f"🧹 Progress cleaned up for: {filename}")

    threading.Thread(target=cleanup, daemon=True).start()


@api_bp.route('/set-layout-engine', methods=['POST'])
def set_layout_engine():
    """Sets the preferred layout engine (YOLO or Surya) in the Gazete processor"""
    try:
        # Global processor kontrolü
        if not processor or not hasattr(processor, 'gazete_processor') or not processor.gazete_processor:
            return jsonify({'success': False, 'error': 'Gazete processor is not initialized'}), 200

        data = request.get_json(silent=True) or {}
        engine = str(data.get('engine', 'yolo')).lower().strip()

        if engine not in ['yolo', 'surya']:
            return jsonify({'success': False, 'error': 'Invalid engine selection. Use "yolo" or "surya"'}), 400

        # GazeteOCRProcessor içindeki engine değişkenini günceller
        processor.gazete_processor.layout_engine = engine
        
        return jsonify({
            'success': True,
            'current_engine': engine,
            'message': f'Layout engine switched to {engine.upper()}'
        }), 200

    except Exception as e:
        print(f"Error setting layout engine: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
    

@api_bp.route('/database-stats', methods=['GET'])
def get_database_stats():
    """Database istatistiklerini getir"""
    try:
        if not DATABASE_INTEGRATION_AVAILABLE:
            return jsonify({
                'database_enabled': False,
                'message': 'Database entegrasyonu kullanılamıyor'
            }), 200

        if not is_database_integration_enabled():
            return jsonify({
                'database_enabled': False,
                'message': 'Database bağlantısı yok'
            }), 200

        stats = get_system_statistics()
        return jsonify(stats), 200

    except Exception as e:
        return jsonify({
            'error': f'İstatistik hatası: {str(e)}',
            'database_enabled': False
        }), 500


@api_bp.route('/status', methods=['GET'])
def get_status():
    """
    UI, 'status' alanını bekliyor: 'ready' | 'initializing' | 'error'
    Ayrıca detector/recognizer/layout bayraklarını da rapor ediyoruz.
    """
    try:
        if processor is None:
            return jsonify({
                'ok': True,
                'status': 'initializing',
                'api': SURYA_API,
                'message': 'SuryaOCR Processor is starting up...'
            }), 200

        api_type = SURYA_API
        has_det = getattr(processor, 'has_detection', False) and (
            getattr(processor, 'detector', None) is not None if api_type == "new" else True
        )
        has_rec = getattr(processor, 'has_recognition', False) and (
            getattr(processor, 'recognizer', None) is not None if api_type == "new" else True
        )
        has_layout = getattr(processor, 'has_layout', False) and (
            getattr(processor, 'layout_predictor', None) is not None if api_type == "new" else False
        )

        # Basit durum kuralı: en az detection yüklenmişse 'ready'
        status = 'ready' if has_det else 'initializing'

        # Database durumu
        db_status = {
            'available': DATABASE_INTEGRATION_AVAILABLE,
            'enabled': is_database_integration_enabled() if DATABASE_INTEGRATION_AVAILABLE else False
        }

        if DATABASE_INTEGRATION_AVAILABLE and is_database_integration_enabled():
            try:
                stats = get_system_statistics()
                db_status.update({
                    'total_documents': stats.get('total_documents', 0),
                    'total_jobs': stats.get('processing_jobs', 0)
                })
            except:
                pass

        return jsonify({
            'ok': True,
            'status': status,
            'api': api_type,
            'gpu': processor.gpu_info if hasattr(processor, 'gpu_info') else None,
            'detection': has_det,
            'recognition': has_rec,
            'layout': has_layout,
            'languages': getattr(processor, 'supported_languages', []),
            'database': db_status
        }), 200
    except Exception as e:
        return jsonify({'ok': False, 'status': 'error', 'error': str(e)}), 500


@api_bp.route('/preprocessed-info/<job_id>', methods=['GET'])
def get_preprocessed_info(job_id: str):
    """
    Gets information about a completed preprocessing job, specifically the output file path.
    Uses the job_results dictionary imported from on_isleme_main.
    """
    if not PREPROCESSING_AVAILABLE:
        return jsonify({'success': False, 'error': 'Preprocessing module not available'}), 404

    # Access the shared job_results dictionary
    result_info = preprocessing_job_results.get(job_id)

    if not result_info or result_info.get("status") != "completed":
        return jsonify({'success': False, 'error': 'Preprocessing job not found or not completed'}), 404

    output_file_path = result_info.get("output_file")
    original_filename = result_info.get("original_filename", "unknown_file")  # Get original name if stored
    page_count = result_info.get("total_processed_pages", 1)  # Get processed page count

    if not output_file_path or not os.path.exists(output_file_path):
        return jsonify({'success': False, 'error': 'Preprocessed output file not found'}), 404

    return jsonify({
        'success': True,
        'job_id': job_id,
        'output_file_path': str(output_file_path),
        'original_filename': original_filename,
        'page_count': page_count,
        'message': 'Preprocessing info retrieved successfully'
    }), 200


@api_bp.route('/upload', methods=['POST'])
def upload_file():
    """
    Dosya yükleme: Hash tabanlı tekil kayıt.
    RTX 5000 sistemi için optimize edilmiş I/O.
    """
    try:
        from hashlib import sha256
        from pathlib import Path
        import os, re
        
        if 'file' not in request.files:
            return jsonify({'error': 'Dosya bulunamadı'}), 400

        file = request.files['file']
        if not file or file.filename.strip() == '':
            return jsonify({'error': 'Dosya seçilmedi'}), 400

        original_name = file.filename
        ext = Path(original_name).suffix.lower()

        allowed_exts = {'.pdf', '.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'}
        if ext not in allowed_exts:
            return jsonify({'error': f'Desteklenmeyen dosya tipi: {ext}'}), 400

        backend_file_path = Path(__file__).resolve()
        app_dir = backend_file_path.parent.parent
        
        if ext == '.pdf':
            base_dir = app_dir / "database" / "veriler" / "pdf"
        else:
            base_dir = app_dir / "database" / "veriler" / "images"

        # Dosyayı hafızaya oku
        data = file.read()
        if not data: return jsonify({'error': 'Boş dosya'}), 400

        digest = sha256(data).hexdigest()
        hash_prefix = digest[:12]
        size_bytes = len(data)

        def slugify(name: str) -> str:
            stem = Path(name).stem.strip()
            stem = re.sub(r"[^\w\s-]", "", stem)
            stem = re.sub(r"\s+", "_", stem)
            return stem[:100] if len(stem) > 100 else stem

        safe_stem = slugify(original_name) or "document"
        
        # SADECE BU İSİMLE KAYIT YAP (Orijinal ismi kaydetme)
        dest_name = f"{safe_stem}_{hash_prefix}{ext}"
        dest_path = base_dir / dest_name
        deduplicated = False
        
        base_dir.mkdir(parents=True, exist_ok=True)
        print(f"DEBUG YAZMA KONTROLÜ: Hashed İsim: {dest_name}, Orijinal İsim: {original_name}. Hedef Yol: {dest_path}")

        if dest_path.exists():
            deduplicated = True
        else:
            with open(dest_path, "wb") as f_out:
                f_out.write(data)

        # Önizleme (Disk I/O yapmadan)
        preview_image_url = None
        try:
            if ext == '.pdf':
                with fitz.open(stream=data, filetype="pdf") as pdf_doc:
                    page = pdf_doc[0]
                    target_width = 400
                    zoom = target_width / page.rect.width
                    matrix = fitz.Matrix(zoom, zoom)
                    pix = page.get_pixmap(matrix=matrix, alpha=False)
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    preview_image_url = _create_base64_preview(img, format="JPEG", quality=75)
            
            elif ext in allowed_exts:
                import io
                img = Image.open(io.BytesIO(data))
                img.thumbnail((400, 600))
                preview_image_url = _create_base64_preview(img, format="JPEG", quality=75)

        except Exception as e:
            print(f"⚠️ Önizleme hatası: {e}")

        response_data = {
            'file_id': dest_path.name,
            'filename': dest_path.name,
            'original_name': original_name,
            'file_path': str(dest_path),
            'size': size_bytes,
            'extension': ext,
            'sha256': digest,
            'deduplicated': deduplicated,
            'preview_image_url': preview_image_url
        }
        return jsonify(response_data), 200

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': f'Dosya yükleme hatası: {str(e)}'}), 500


@api_bp.route('/page-preview', methods=['POST'])
def get_page_preview():
    """
    Bir dosyanın belirli bir sayfasının önizlemesini Base64 olarak döndürür.
    """
    try:
        data = request.get_json(silent=True) or {}
        file_path = str(data.get('file_path', '')).strip()
        page_number = int(data.get('page_number', 1))

        if not file_path or not os.path.exists(file_path):
            return jsonify({'success': False, 'error': 'Geçersiz dosya yolu'}), 400

        if page_number < 1:
            page_number = 1

        preview_image_url = None
        ext = Path(file_path).suffix.lower()

        if ext == '.pdf':
            pdf_doc = fitz.open(file_path)

            # Sayfa numarasının geçerli olduğundan emin ol
            if page_number > pdf_doc.page_count:
                page_number = pdf_doc.page_count  # Son sayfayı göster

            page = pdf_doc[page_number - 1]  # 0-indeksli

            # Küçük bir önizleme için yeniden boyutlandır (örn. 400px genişlik)
            target_width = 400
            zoom = target_width / page.rect.width
            matrix = fitz.Matrix(zoom, zoom)

            pix = page.get_pixmap(matrix=matrix, alpha=False)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            preview_image_url = _create_base64_preview(img, format="JPEG", quality=70)
            pdf_doc.close()

        elif ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif']:
            # Eğer dosya bir resimse, her zaman aynı resmi döndür
            # (veya /upload'dan gelen ilk önizlemeyi kullan)
            # Bu endpoint çoğunlukla PDF'ler için anlamlıdır.
            # Yine de, tutarlılık için resmin kendisini döndürelim.
            img = Image.open(file_path)
            img.thumbnail((400, 600))
            preview_image_url = _create_base64_preview(img, format="JPEG", quality=70)

        else:
            return jsonify({'success': False, 'error': 'Desteklenmeyen dosya tipi'}), 400

        if preview_image_url:
            return jsonify({
                'success': True,
                'page_number': page_number,
                'preview_image_url': preview_image_url
            }), 200
        else:
            return jsonify({'success': False, 'error': 'Önizleme oluşturulamadı'}), 500

    except Exception as e:
        import traceback
        print(f"❌ Sayfa önizleme hatası: {str(e)}")
        print(traceback.format_exc())


@api_bp.route('/process', methods=['POST'])
def process_document():
    """
    Belge işleme endpoint'i.
    - Her zaman JSON-serializable yanıt döndürür.
    - Hata olsa bile 200 + success:false (UI tek akış).
    - input sanitize: output_formats kesin string listesine indirilir.
    - MODIFIED: Accepts optional 'preprocessed_job_id' to use preprocessed file.
    - FIXED: Progress key (filename_for_progress) artık frontend'den gelen
             'original_filename_for_stream' ile eşleştirildi.
    """
    import traceback
    import time

    start_time = time.time()  # Start timer early
    filename_for_progress = None  # Progress tracking için kullanılacak dosya adı
    actual_file_path_to_process = None  # İşlenecek dosyanın yolu

    try:
        if not processor:
            # Processor henüz hazır değilse hata döndür
            return jsonify({'success': False, 'error': 'Processor henüz hazır değil'}), 503  # Service Unavailable

        data = request.get_json(silent=True) or {}
        file_path_from_request = str(data.get('file_path', '')).strip()
        process_mode = str(data.get('process_mode', 'ocr')).lower().strip()
        preprocessed_job_id = data.get('preprocessed_job_id')  # Ön işleme ID'si

        # --- ÇÖZÜM: Progress key'ini doğrudan request'ten al ---
        filename_for_progress = data.get('original_filename_for_stream')

        # --- Girdi dosyasının yolunu belirle ---
        if preprocessed_job_id and PREPROCESSING_AVAILABLE:
            print(f"✅ Preprocessed job ID received: {preprocessed_job_id}")
            preprocessed_info = preprocessing_job_results.get(preprocessed_job_id)

            if preprocessed_info and preprocessed_info.get("status") == "completed" and preprocessed_info.get(
                    "output_file"):
                actual_file_path_to_process = preprocessed_info["output_file"]

                # --- DÜZELTME: Progress key'ini request'ten gelenle eşleştir ---
                if not filename_for_progress:
                    # Fallback (eğer frontend göndermezse, ki göndermeli)
                    original_filename = preprocessed_info.get("original_filename",
                                                              Path(actual_file_path_to_process).name)
                    filename_for_progress = original_filename
                    print(f"⚠️ 'original_filename_for_stream' request'te eksik. Fallback: {filename_for_progress}")

                print(f"➡️ Using preprocessed file: {actual_file_path_to_process}")
                print(f"   Filename for progress tracking (from request): {filename_for_progress}")
            else:
                print(f"⚠️ Preprocessed job ID {preprocessed_job_id} not found or invalid.")
                if not file_path_from_request:
                    return jsonify({'success': False, 'error': 'Ön işlenmiş iş geçersiz ve dosya yolu sağlanmadı'}), 400
                actual_file_path_to_process = file_path_from_request
                # Fallback progress key
                if not filename_for_progress:
                    filename_for_progress = Path(actual_file_path_to_process).name
                print(f"   Fallback to requested path: {actual_file_path_to_process}")
        else:
            # Normal akış
            if not file_path_from_request:
                return jsonify({'success': False, 'error': 'file_path gerekli'}), 400
            actual_file_path_to_process = file_path_from_request
            # Normal akışta progress key'i request'ten al (frontend bunu 'mydocument_hash.pdf' olarak göndermeli)
            if not filename_for_progress:
                filename_for_progress = Path(actual_file_path_to_process).name
                print(f"⚠️ 'original_filename_for_stream' request'te eksik. Fallback: {filename_for_progress}")

            print(f"➡️ Using file path from request: {actual_file_path_to_process}")
            print(f"   Filename for progress tracking (from request): {filename_for_progress}")

        # --- Çıktı formatlarını normalize et ---
        raw_formats = data.get('output_formats', ['md', 'xml'])
        allowed_formats = ['md', 'xml']
        output_formats = []
        if isinstance(raw_formats, list):
            for fmt in raw_formats:
                if isinstance(fmt, str) and fmt.strip().lower() in allowed_formats:
                    fmt_clean = fmt.strip().lower()
                    if fmt_clean not in output_formats:  # Tekrarları önle
                        output_formats.append(fmt_clean)
        elif isinstance(raw_formats, str) and raw_formats.strip().lower() in allowed_formats:
            output_formats = [raw_formats.strip().lower()]

        if not output_formats: output_formats = ['md']  # Varsayılan: md

        # --- İşlem durumunu başlat (filename_for_progress kullanarak) ---
        if not filename_for_progress:
            # Bu olmamalı ama son bir güvenlik kontrolü
            filename_for_progress = f"fallback_{time.time()}"
            print(f"❌ KRİTİK HATA: filename_for_progress ayarlanamadı. Fallback: {filename_for_progress}")

        if filename_for_progress not in processing_status:
            processing_status[filename_for_progress] = {
                'progress': 0,
                'status': 'Başladı',
                'current_page': 0,
                'total_pages': 0,
                'started': True,
                'start_time': start_time,
                'cancelled': False  # İptal bayrağı ekle
            }
        else:
            # Eğer zaten varsa, iptal edilmediğinden emin ol ve sıfırla
            processing_status[filename_for_progress].update({
                'progress': 0,
                'status': 'Yeniden Başladı',
                'current_page': 0,
                'total_pages': 0,
                'started': True,
                'start_time': start_time,
                'cancelled': False  # İptal bayrağını temizle
            })

        # --- processor.process_file çağrısı ---
        # Pass the whole data dict as metadata source
        result = processor.process_file(
            actual_file_path_to_process,
            process_mode,
            output_formats,
            progress_key=filename_for_progress,
            user_metadata_dict=data
        )

        # --- Sonucu JSON uyumlu hale getir ---
        def _to_jsonable(obj):
            if isinstance(obj, Path): return str(obj)
            if isinstance(obj, dict): return {str(k): _to_jsonable(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)): return [_to_jsonable(x) for x in obj]
            if hasattr(obj, 'item'):  # Numpy types
                try:
                    return obj.item()
                except:
                    pass
            try:  # Son çare: string'e çevir
                json.dumps(obj)
                return obj
            except TypeError:
                return str(obj)

        safe_result = _to_jsonable(result)

        # İşlem süresini ve başarı durumunu ekle (eğer eksikse)
        if 'processing_time' not in safe_result:
            safe_result['processing_time'] = time.time() - start_time
        if 'success' not in safe_result:
            safe_result['success'] = True  # Hata yoksa başarılı varsay

        # Başarı durumunu güncelle (hata yoksa)
        if safe_result.get('success'):
            update_progress(filename_for_progress, 100, 'İşlem başarıyla tamamlandı!',
                            safe_result.get('page_count', 0), safe_result.get('page_count', 0))
            cleanup_progress_after_delay(filename_for_progress, 30)  # Başarı durumunda daha uzun bekle

        # Yanıtı döndür (başarılı durumda 200)
        return jsonify(safe_result), 200

    except Exception as e:
        # Hata durumunda traceback'i logla
        print(f"❌ /api/process hata traceback:\n{traceback.format_exc()}")
        error_message = f'{type(e).__name__}: {str(e)}'

        # Progress durumunu hata olarak güncelle (eğer filename biliniyorsa)
        if filename_for_progress:
            update_progress(filename_for_progress, -1, f'Hata: {error_message}', 0, 0,
                            error=True)  # Hata bayrağını gönder
            cleanup_progress_after_delay(filename_for_progress, 10)  # Hata durumunda daha hızlı temizle

        # Hata yanıtını döndür (başarısız durumda 500)
        return jsonify({'success': False, 'error': error_message}), 500


@api_bp.route('/download/<format_type>', methods=['POST'])
def download_result(format_type):
    """Sonuç dosyasını indirme endpoint'i"""
    try:
        data = request.get_json()
        content = data.get('content')
        filename = data.get('filename', 'document')

        if not content:
            return jsonify({'error': 'İçerik bulunamadı'}), 400

        # Geçici dosya oluştur
        temp_file = tempfile.NamedTemporaryFile(
            mode='w',
            suffix=f'.{format_type}',
            delete=False,
            encoding='utf-8'
        )
        temp_file.write(content)
        temp_file.close()

        # MIME type belirleme
        mime_types = {
            'md': 'text/markdown',
            'xml': 'application/xml',
            'txt': 'text/plain'
        }

        return send_file(
            temp_file.name,
            as_attachment=True,
            download_name=f'{filename}.{format_type}',
            mimetype=mime_types.get(format_type, 'application/octet-stream')
        )

    except Exception as e:
        return jsonify({'error': f'İndirme hatası: {str(e)}'}), 500


@api_bp.route('/download-zip', methods=['POST'])
def download_zip():
    """
    Belgeleri sıkıştırıp (zip) indirir.
    Frontend'den { filename_base: str, files: { ext: content } } alır.
    Stateless çalışır (DB gerekmez).
    """
    try:
        data = request.get_json() or {}
        filename_base = data.get('filename_base', 'document')
        files = data.get('files', {})

        if not files:
            return jsonify({'error': 'Dosya içeriği bulunamadı'}), 400

        # Memory buffer for zip
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for ext, content in files.items():
                if content:
                    # Dosya adını oluştur: base.ext
                    fname = f"{filename_base}.{ext}"
                    zip_file.writestr(fname, content)

        zip_buffer.seek(0)
        
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f"{filename_base}.zip"
        )

    except Exception as e:
        print(f"Zip oluşturma hatası: {e}")
        return jsonify({'error': f'Zip hatası: {str(e)}'}), 500


@api_bp.route('/metadata', methods=['POST'])
def set_metadata():
    """Set document metadata for processing"""
    try:
        if not processor:
            return jsonify({'success': False, 'error': 'Processor henüz hazır değil'}), 200

        data = request.get_json(silent=True) or {}

        # Create metadata from form data
        metadata = create_metadata_from_form(data)

        # Set metadata in processor
        processor.set_document_metadata(metadata)

        return jsonify({
            'success': True,
            'message': 'Metadata başarıyla ayarlandı',
            'metadata': metadata.to_dict()
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'error': f'Metadata ayarlama hatası: {str(e)}'}), 200


@api_bp.route('/metadata', methods=['GET'])
def get_metadata():
    """Get current document metadata"""
    try:
        if not processor:
            return jsonify({'success': False, 'error': 'Processor henüz hazır değil'}), 200

        metadata_json = processor.get_metadata_json()

        return jsonify({
            'success': True,
            'metadata': json.loads(metadata_json)
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'error': f'Metadata okuma hatası: {str(e)}'}), 200


@api_bp.route('/metadata', methods=['DELETE'])
def clear_metadata():
    """Clear document metadata"""
    try:
        if not processor:
            return jsonify({'success': False, 'error': 'Processor henüz hazır değil'}), 200

        processor.clear_document_metadata()

        return jsonify({
            'success': True,
            'message': 'Metadata temizlendi'
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'error': f'Metadata temizleme hatası: {str(e)}'}), 200


@api_bp.route('/fetch-metadata', methods=['POST'])
def fetch_metadata():
    """Fetch metadata from external APIs using identifiers"""
    try:
        data = request.get_json(silent=True) or {}
        identifier_type = data.get('identifier_type', '').strip().lower()
        identifier = data.get('identifier', '').strip()

        if not identifier_type or not identifier:
            return jsonify({
                'success': False,
                'error': 'Identifier type ve identifier gerekli'
            }), 200

        # Import the async function
        from DocumentMetadata import fetch_metadata_by_identifier
        import asyncio

        # Run async function
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            metadata_result = loop.run_until_complete(
                fetch_metadata_by_identifier(identifier_type, identifier)
            )
            loop.close()
        except Exception as async_error:
            return jsonify({
                'success': False,
                'error': f'API çağrısı başarısız: {str(async_error)}'
            }), 200

        if metadata_result:
            return jsonify({
                'success': True,
                'metadata': metadata_result
            }), 200
        else:
            # Fallback demo data for DOI
            if identifier_type == 'doi' and '10.' in identifier:
                demo_metadata = {
                    'metadata_type': 'article',
                    'title': 'Örnek Akademik Makale Başlığı',
                    'author': 'Dr. Ahmet Yılmaz, Prof. Dr. Ayşe Kaya',
                    'publication': 'Bilimsel Araştırmalar Dergisi',
                    'volume': '15',
                    'issue': '3',
                    'pages': '245-267',
                    'date': '2023-06-15',
                    'doi': identifier,
                    'language': 'tr'
                }
                return jsonify({
                    'success': True,
                    'metadata': demo_metadata,
                    'note': 'Demo metadata (gerçek API entegrasyonu için backend gerekli)'
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'error': 'Metadata bulunamadı'
                }), 200

    except Exception as e:
        print(f"Fetch metadata error: {e}")
        return jsonify({
            'success': False,
            'error': f'Sunucu hatası: {str(e)}'
        }), 200


@api_bp.route('/metadata-schema', methods=['GET'])
def get_metadata_schema_endpoint():
    """Get metadata schema for frontend validation"""
    try:
        schema = get_metadata_schema()
        return jsonify({
            'success': True,
            'schema': schema
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Schema hatası: {str(e)}'
        }), 200


def get_eta_info(status_info: dict):
    """
    Gelişmiş ETA sistemi - Sayfa bazlı tahmin ve geriye sayım
    Düzeltildi: Son sayfa hesabı ve ani süre düşüşleri optimize edildi.
    """
    eta_seconds, eta_text = None, "Hesaplanıyor..."

    try:
        if not (status_info.get("started") and
                status_info.get("start_time") and
                status_info.get("total_pages", 0) > 0):
            return eta_seconds, eta_text

        current_page = int(status_info.get("current_page", 0))
        total_pages = int(status_info.get("total_pages", 0))
        page_times = status_info.get("page_completion_times", {})
        completed_count = len(page_times)
        now_time = time.time()

        # Henüz hiç sayfa tamamlanmadıysa
        if completed_count == 0:
            return None, "Başlıyor..."

        # Ortalama sayfa süresini hesapla
        times_values = list(page_times.values())
        avg_page_time = sum(times_values) / completed_count

        # İYİLEŞTİRME: İlk sayfa sendromunu (Initialization overhead) engelle
        # Eğer en az 2 sayfa tamamlandıysa ve ilk sayfa ortalamanın çok üstündeyse (örn: >2 kat)
        # ilk sayfayı ortalamadan çıkar.
        if completed_count >= 2:
            t1 = page_times.get(1) # veya listeden ilk eleman
            # İlk sayfanın listede 1 numaralı anahtarla olup olmadığını kontrol edelim
            # page_completion_times {page_num: seconds} şeklindedir.
            if 1 in page_times:
                other_sum = sum(times_values) - page_times[1]
                other_avg = other_sum / (completed_count - 1)
                # Eğer ilk sayfa diğerlerinin ortalamasından %50 daha uzun sürdüyse (1.5x)
                if page_times[1] > (other_avg * 1.5):
                    avg_page_time = other_avg
                    # print(f"ℹ️ ETA: İlk sayfa (init) ortalamadan çıkarıldı. ({page_times[1]:.1f}s vs {other_avg:.1f}s)")

        # 1. Gelecek (Henüz başlanmamış) Sayfalar
        # Örn: 10 sayfa var, 4. sayfayı işliyoruz. Gelecek sayfalar: 5, 6, 7, 8, 9, 10 -> 6 tane
        # Logic: total_pages - current_page
        future_pages_count = max(0, total_pages - current_page)
        remaining_future = future_pages_count * avg_page_time

        # 2. Mevcut Sayfa (İşlenmekte olan)
        # Geçen süre
        page_start_time = status_info.get("page_start_time", now_time)
        current_elapsed = max(0, now_time - page_start_time)
        
        # Mevcut sayfa için kalan tahmini süre
        # Eğer geçen süre ortalamadan azsa: (Ortalama - Geçen)
        # Eğer geçen süre ortalamayı geçtiyse: En az 1 sn daha var diyelim (sıfırlanmasın)
        remaining_current = max(1, avg_page_time - current_elapsed)

        # Toplam Kalan
        total_remaining = remaining_future + remaining_current

        eta_seconds = int(total_remaining)

        # Metin formatı
        if eta_seconds < 60:
            eta_text = f"{eta_seconds} sn"
        elif eta_seconds < 3600:
            m, s = divmod(eta_seconds, 60)
            eta_text = f"{m} dk {s} sn"
        else:
            h, rem = divmod(eta_seconds, 3600)
            m, s = divmod(rem, 60)
            eta_text = f"{h} sa {m} dk"

        return eta_seconds, eta_text

    except Exception as e:
        print(f"⚠️ ETA Error: {e}")
        return None, "Hesaplanıyor..."



@api_bp.route('/cancel/<filename>', methods=['POST'])
def cancel_processing(filename):
    """İşlemi iptal et"""
    try:
        if filename in processing_status:
            processing_status[filename].update({
                'cancelled': True,
                'status': 'İptal edildi',
                'progress': 0
            })

        return jsonify({'success': True, 'message': 'İşlem iptal edildi'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@api_bp.route('/progress-stream/<filename>')
def progress_stream(filename):
    """
    SSE endpoint - Real-time progress updates
    """

    def generate():
        # Queue oluştur
        if filename not in progress_queues:
            progress_queues[filename] = queue.Queue(maxsize=100)

        q = progress_queues[filename]

        print(f"🔌 SSE: Client connected for {filename}")

        # İlk durumu gönder
        initial_status = processing_status.get(filename, {
            'progress': 0,
            'status': 'Bağlanıldı...',
            'current_page': 0,
            'total_pages': 0,
            'started': False
        })

        yield f"data: {json.dumps(initial_status)}\n\n"

        # Progress updates'i stream et
        timeout_counter = 0
        max_timeout = 600  # 10 dakika (600 * 1 saniye)

        while True:
            try:
                # Queue'dan veri al (1 saniye timeout)
                progress_data = q.get(timeout=1.0)

                # JSON'a çevir ve gönder
                yield f"data: {json.dumps(progress_data)}\n\n"

                # Reset timeout counter
                timeout_counter = 0

                # %100 ise bağlantıyı kapat
                if progress_data.get('progress', 0) >= 100:
                    print(f"✅ SSE: Processing completed for {filename}")
                    # Son mesajı gönder
                    yield f"data: {json.dumps({'completed': True})}\n\n"
                    break

            except queue.Empty:
                # Timeout - heartbeat gönder
                timeout_counter += 1

                # Her 30 saniyede bir heartbeat
                if timeout_counter % 30 == 0:
                    yield f": heartbeat\n\n"

                # Max timeout aşıldıysa kapat
                if timeout_counter >= max_timeout:
                    print(f"⏱️ SSE: Timeout for {filename}")
                    yield f"data: {json.dumps({'timeout': True})}\n\n"
                    break

            except GeneratorExit:
                print(f"🔌 SSE: Client disconnected for {filename}")
                break

        # Cleanup
        if filename in progress_queues:
            del progress_queues[filename]
        print(f"🧹 SSE: Cleaned up queue for {filename}")

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )


@api_bp.route('/progress/<filename>', methods=['GET'])
def get_processing_progress(filename):
    """
    Fallback progress endpoint (SSE desteklemeyen clientlar için)
    Artık sadece son durumu döndürür, real-time için /progress-stream kullanın
    """
    try:
        status_info = processing_status.get(filename, {
            'progress': 0,
            'status': 'Bekliyor...',
            'current_page': 0,
            'total_pages': 0,
            'started': False,
            'message': 'Bu endpoint artık polling için değil, SSE kullanın: /progress-stream/<filename>'
        })

        # ETA ekle
        eta_seconds, eta_text = get_eta_info(status_info)
        status_info = {**status_info, 'eta_seconds': eta_seconds, 'eta_text': eta_text}

        return jsonify(status_info), 200
    except Exception as e:
        print(f"❌ Progress endpoint error: {e}")
        return jsonify({'error': f'Progress error: {str(e)}'}), 500


@api_bp.route('/detect-newspaper', methods=['POST'])
def detect_newspaper():
    """
    Dosyanın gazete olup olmadığını tespit et (OCR yapmadan)
    """
    try:
        if not processor or not processor.gazete_processor:
            return jsonify({
                'success': False,
                'error': 'Gazete processor hazır değil'
            }), 200

        data = request.get_json(silent=True) or {}
        file_path = str(data.get('file_path', '')).strip()

        if not file_path:
            return jsonify({'success': False, 'error': 'file_path boş'}), 200

        from pathlib import Path
        p = Path(file_path)

        if not p.exists():
            return jsonify({'success': False, 'error': 'Dosya bulunamadı'}), 200

        # Dosyayı yükle
        file_extension = p.suffix.lower()
        images = []

        if file_extension in ['.pdf']:
            images = processor.pdf_to_images(str(p))
        elif file_extension in ['.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp', '.webp']:
            from PIL import Image
            image = Image.open(str(p))
            if image.mode not in ['RGB', 'L']:
                image = image.convert('RGB')
            images = [image]
        else:
            return jsonify({
                'success': False,
                'error': f'Desteklenmeyen dosya formatı: {file_extension}'
            }), 200

        # Gazete tespiti
        is_newspaper = processor.gazete_processor.is_newspaper(images, threshold=3)

        return jsonify({
            'success': True,
            'is_newspaper': is_newspaper,
            'document_type': 'newspaper' if is_newspaper else 'standard',
            'page_count': len(images)
        }), 200

    except Exception as e:
        print(f"❌ Gazete tespiti hatası: {e}")
        return jsonify({
            'success': False,
            'error': f'Tespit hatası: {str(e)}'
        }), 200


@api_bp.route('/gazete-status', methods=['GET'])
def get_gazete_status():
    """
    Gazete processor durumunu kontrol et
    """
    try:
        gazete_available = (processor is not None and
                            processor.gazete_processor is not None and
                            processor.gazete_processor.yolo_available)

        status = {
            'gazete_processor_available': gazete_available,
            'yolo_available': gazete_available,
            'message': 'Gazete tespiti aktif' if gazete_available else 'Gazete tespiti kullanılamıyor'
        }

        if not gazete_available and processor:
            backend_dir = Path(__file__).parent.resolve()
            yolo_model_path = backend_dir / "models" / "doclayout_yolo_docstructbench_imgsz1024.pt"

            if not yolo_model_path.exists():
                status['reason'] = 'YOLO model dosyası bulunamadı'
                status['model_path'] = str(yolo_model_path)
                status['download_url'] = 'https://huggingface.co/juliozhao/DocLayout-YOLO-DocStructBench'

        return jsonify(status), 200

    except Exception as e:
        return jsonify({
            'gazete_processor_available': False,
            'error': str(e)
        }), 200


@api_bp.route('/process-newspaper', methods=['POST'])
def process_newspaper_only():
    """
    Sadece gazete işleme için özel endpoint
    """
    try:
        if not processor or not processor.gazete_processor:
            return jsonify({
                'success': False,
                'error': 'Gazete processor hazır değil'
            }), 200

        data = request.get_json(silent=True) or {}
        file_path = str(data.get('file_path', '')).strip()

        if not file_path:
            return jsonify({'success': False, 'error': 'file_path boş'}), 200

        from pathlib import Path
        p = Path(file_path)

        if not p.exists():
            return jsonify({'success': False, 'error': 'Dosya bulunamadı'}), 200

        filename = p.name

        # Progress başlat
        processing_status[filename] = {
            'progress': 0,
            'status': 'Gazete işleme başladı',
            'current_page': 0,
            'total_pages': 0,
            'started': True,
            'start_time': time.time()
        }

        # Dosyayı yükle
        update_progress(filename, 5, 'Gazete dosyası yükleniyor...', 0, 0)

        file_extension = p.suffix.lower()
        images = []

        if file_extension in ['.pdf']:
            update_progress(filename, 10, 'PDF sayfa ayırımı...', 0, 0)
            images = processor.pdf_to_images(str(p))
        elif file_extension in ['.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp', '.webp']:
            from PIL import Image
            image = Image.open(str(p))
            if image.mode not in ['RGB', 'L']:
                image = image.convert('RGB')
            images = [image]
        else:
            return jsonify({
                'success': False,
                'error': f'Desteklenmeyen dosya formatı: {file_extension}'
            }), 200

        total_pages = len(images)

        update_progress(filename, 15, f'{total_pages} sayfa yüklendi', 0, total_pages)

        # Gazete işleme
        ocr_results = processor._process_newspaper_ocr(images, filename, total_pages)

        # Çıktılar oluştur
        update_progress(filename, 80, 'Markdown formatı oluşturuluyor...', total_pages, total_pages)
        md_output = processor.generate_markdown_output(ocr_results, filename)

        update_progress(filename, 90, 'XML formatı oluşturuluyor...', total_pages, total_pages)
        xml_output = processor.generate_xml_output(ocr_results, filename)

        # Sonuç
        result = {
            'success': True,
            'filename': filename,
            'file_path': str(p),
            'process_mode': 'newspaper_ocr',
            'document_type': 'newspaper',
            'page_count': total_pages,
            'ocr_results': ocr_results,
            'outputs': {
                'md': md_output,
                'xml': xml_output
            },
            'processing_time': time.time() - processing_status[filename]['start_time']
        }

        update_progress(filename, 100, 'Gazete işleme tamamlandı!', total_pages, total_pages)
        cleanup_progress_after_delay(key_for_updates, 5)

        return jsonify(result), 200

    except Exception as e:
        if filename:
            update_progress(key_for_updates, 0, f'Hata: {str(e)}', 0, 0)
            cleanup_progress_after_delay(filename, 5)

        print(f"❌ Gazete işleme hatası: {e}")
        import traceback
        print(traceback.format_exc())

        return jsonify({
            'success': False,
            'error': f'İşleme hatası: {str(e)}'
        }), 200


@api_bp.route('/layout-detection', methods=['POST'])
def detect_layout():
    """
    Belirli bir sayfa için layout tespiti yap - SADECE o sayfayı yükle
    """
    try:
        data = request.get_json(silent=True) or {}
        file_path = str(data.get('file_path', '')).strip()
        page_number = int(data.get('page_number', 1))
        method = str(data.get('method', 'both'))  # 'surya', 'yolo', 'both'

        if not file_path:
            return jsonify({'success': False, 'error': 'file_path boş'}), 200

        p = Path(file_path)
        if not p.exists():
            return jsonify({'success': False, 'error': 'Dosya bulunamadı'}), 200

        # ✅ SADECE İSTENEN SAYFAYI YÜKLE
        file_extension = p.suffix.lower()

        if file_extension in ['.pdf']:
            # ✅ PDF'den SADECE belirtilen sayfayı yükle
            print(f"📄 PDF'den sayfa {page_number} yükleniyor...")

            try:
                pdf_document = fitz.open(str(p))
                total_pages = pdf_document.page_count

                if page_number < 1 or page_number > total_pages:
                    pdf_document.close()
                    return jsonify({
                        'success': False,
                        'error': f'Geçersiz sayfa numarası: {page_number} (toplam: {total_pages})'
                    }), 200

                # ✅ SADECE belirtilen sayfayı render et
                page = pdf_document[page_number - 1]  # 0-indexed
                zoom = 3.3
                matrix = fitz.Matrix(zoom, zoom)
                pixmap = page.get_pixmap(matrix=matrix)

                # PIL Image'e çevir
                img_data = pixmap.tobytes("ppm")
                target_image = Image.open(BytesIO(img_data))

                if target_image.mode != 'RGB':
                    target_image = target_image.convert('RGB')

                pdf_document.close()

                print(f"✅ PDF sayfa {page_number} yüklendi")

            except Exception as pdf_error:
                return jsonify({
                    'success': False,
                    'error': f'PDF yükleme hatası: {str(pdf_error)}'
                }), 200

        elif file_extension in ['.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp', '.webp']:
            # Tek görsel dosyası
            target_image = Image.open(str(p))
            if target_image.mode not in ['RGB', 'L']:
                target_image = target_image.convert('RGB')
            total_pages = 1

        else:
            return jsonify({
                'success': False,
                'error': f'Desteklenmeyen format: {file_extension}'
            }), 200

        # Layout tespiti yap
        if method == 'both':
            results = processor.get_layout_comparison(target_image)
        elif method == 'surya':
            if processor.has_layout:
                page_layout = processor.analyze_layout(target_image, page_number=page_number)

                if page_layout:
                    # Visualization için dummy result oluştur
                    results = {
                        'surya': {
                            'detections': [],
                            'layout_info': page_layout
                        }
                    }
                else:
                    return jsonify({
                        'success': False,
                        'error': 'Surya layout analizi başarısız'
                    }), 200
            else:
                return jsonify({
                    'success': False,
                    'error': 'Surya layout kullanılamıyor'
                }), 200

        elif method == 'yolo':
            if processor.gazete_processor and processor.gazete_processor.yolo_available:
                yolo_result = processor.gazete_processor.yolo_model(target_image)[0]
                results = {
                    'yolo': processor.visualize_layout(target_image, yolo_result, 'yolo')
                }
            else:
                return jsonify({
                    'success': False,
                    'error': 'YOLO layout kullanılamıyor'
                }), 200
        else:
            return jsonify({'success': False, 'error': 'Geçersiz method'}), 200

        return jsonify({
            'success': True,
            'page_number': page_number,
            'total_pages': total_pages,
            'results': results
        }), 200

    except Exception as e:
        print(f"❌ Layout detection error: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': f'Layout tespit hatası: {str(e)}'
        }), 200


@api_bp.route('/layout-statistics', methods=['POST'])
def get_layout_statistics():
    """
    Tüm sayfalardaki layout istatistiklerini getir
    """
    try:
        data = request.get_json(silent=True) or {}
        file_path = str(data.get('file_path', '')).strip()

        if not file_path:
            return jsonify({'success': False, 'error': 'file_path boş'}), 200

        p = Path(file_path)
        if not p.exists():
            return jsonify({'success': False, 'error': 'Dosya bulunamadı'}), 200

        # Dosyayı yükle
        file_extension = p.suffix.lower()
        images = []

        if file_extension in ['.pdf']:
            images = processor.pdf_to_images(str(p))
        elif file_extension in ['.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp', '.webp']:
            from PIL import Image
            image = Image.open(str(p))
            if image.mode not in ['RGB', 'L']:
                image = image.convert('RGB')
            images = [image]

        statistics = {
            'total_pages': len(images),
            'pages': []
        }

        for page_idx, image in enumerate(images):
            page_stats = {
                'page_number': page_idx + 1,
                'surya': {'count': 0, 'types': {}},
                'yolo': {'count': 0, 'types': {}}
            }

            # Surya stats
            if processor.has_layout:
                try:
                    layout = processor.layout_predictor([image])[0]
                    if hasattr(layout, 'bboxes'):
                        page_stats['surya']['count'] = len(layout.bboxes)
                        for bbox in layout.bboxes:
                            label = str(getattr(bbox, 'label', 'text'))
                            page_stats['surya']['types'][label] = \
                                page_stats['surya']['types'].get(label, 0) + 1
                except Exception as e:
                    print(f"Surya stats error page {page_idx + 1}: {e}")

            # YOLO stats
            if processor.gazete_processor and processor.gazete_processor.yolo_available:
                try:
                    result = processor.gazete_processor.yolo_model(image)[0]
                    page_stats['yolo']['count'] = len(result.boxes)
                    for cls in result.boxes.cls:
                        label = processor.gazete_processor.yolo_model.names[int(cls)]
                        page_stats['yolo']['types'][label] = \
                            page_stats['yolo']['types'].get(label, 0) + 1
                except Exception as e:
                    print(f"YOLO stats error page {page_idx + 1}: {e}")

            statistics['pages'].append(page_stats)

        return jsonify({
            'success': True,
            'statistics': statistics
        }), 200

    except Exception as e:
        print(f"❌ Statistics error: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 200


def update_progress(filename, progress, status, current_page=0, total_pages=0, error=False, preview_image_url=None):  # Hata bayrağı ve önizleme eklendi
    """
    Geliştirilmiş progress tracking - SSE ile real-time güncelleme
    (MONOTONİK YAPI: Yüzde asla geri gitmez)
    """
    if not filename:
        return

    now_ts = time.time()
    prev = processing_status.get(filename, {})

    # --- 1. Hata Durumu (Hemen çık) ---
    if error:
        progress_data = {
            'progress': -1,  # Hata kodu
            'status': str(status or 'Hata oluştu'),
            'current_page': int(current_page or 0),
            'total_pages': int(total_pages or 0),
            'started': prev.get('started', True),
            'error': True,
            'timestamp': now_ts,
            'last_update': now_ts,
            'eta_text': 'Hata',
            'preview_image_url': preview_image_url or prev.get('preview_image_url')
        }
        processing_status[filename] = progress_data
        if filename in progress_queues:
            try:
                progress_queues[filename].put_nowait(progress_data)
                print(f"📡 SSE: Hata gönderildi - {filename} - {status}")
            except queue.Full:
                pass
        return

    # --- 2. Normal İlerleme (Monotonik) ---

    # Önceki ilerlemeyi al
    prev_progress = float(prev.get('progress', 0))

    # Yeni ilerleme değerini belirle
    new_progress = float(max(0, min(100, (progress if progress is not None else prev_progress))))

    # *** MONOTONİK KURAL ***
    # Yeni ilerleme, önceki ilerlemeden küçükse ve 0 değilse (resetleme)
    # ve önceki ilerleme -1 (hata) değilse, YENİ İLERLEMEYİ KULLANMA.
    if (new_progress < prev_progress) and (new_progress != 0) and (prev_progress != -1):
        # print(f"⚠️ Progress gerilemesi engellendi: {prev_progress:.1f}% -> {new_progress:.1f}%. ({status})") # Debug için
        new_progress = prev_progress  # Eski (yüksek) değeri koru

    # --- Sayfa zamanlama (kullanıcının mevcut kodundan alındı) ---
    if 'start_time' not in prev:
        prev['start_time'] = now_ts
    if 'page_completion_times' not in prev:
        prev['page_completion_times'] = {}
    prev_page = prev.get('current_page', 0)
    page_changed = current_page != prev_page and current_page > 0
    if page_changed and prev_page > 0:
        page_duration = now_ts - prev.get('page_start_time', prev['start_time'])
        prev['page_completion_times'][prev_page] = page_duration
        print(f"📋 Sayfa {prev_page} tamamlandı: {page_duration:.1f} saniye")
    if page_changed:
        prev['page_start_time'] = now_ts
    if current_page == 1 and 'page_start_time' not in prev:
        prev['page_start_time'] = prev['start_time']
    if 'initial_eta' not in prev:
        prev['initial_eta'] = None
    if 'eta_start_time' not in prev:
        prev['eta_start_time'] = None
    # --- Sayfa zamanlama sonu ---

    # Progress data oluştur
    progress_data = {
        'progress': new_progress,  # Monotonik olarak güncellenmiş değeri kullan
        'status': str(status or prev.get('status', '')),
        'current_page': int(max(0, current_page or prev.get('current_page', 0))),
        'total_pages': int(max(0, total_pages or prev.get('total_pages', 0))),
        'started': True,
        'start_time': prev['start_time'],
        'page_start_time': prev.get('page_start_time'),
        'page_completion_times': prev['page_completion_times'],
        'initial_eta': prev['initial_eta'],
        'eta_start_time': prev['eta_start_time'],
        'timestamp': now_ts,
        'last_update': now_ts,
        'error': False,  # Hata olmadığını belirt
        'preview_image_url': preview_image_url or prev.get('preview_image_url')
    }

    # ETA hesapla
    eta_seconds, eta_text = get_eta_info(progress_data)
    progress_data['eta_seconds'] = eta_seconds
    progress_data['eta_text'] = eta_text

    # Global state'e kaydet
    processing_status[filename] = progress_data

    # SSE queue'ya gönder
    if filename in progress_queues:
        try:
            progress_queues[filename].put_nowait(progress_data)
            # print(f"📡 SSE: Progress sent - {filename} - {current_page}/{total_pages} - {new_progress:.1f}%") # Debug için
        except queue.Full:
            print(f"⚠️ SSE Queue full for {filename}")

    # Database integration - progress update
    if (DATABASE_INTEGRATION_AVAILABLE and
            is_database_integration_enabled() and
            current_job_id):  # current_job_id global'den okunmalı
        try:
            # Hata durumunda DB'ye 0 göndermek yerine mevcut ilerlemeyi gönder
            db_progress_val = new_progress if not error else prev_progress
            update_job_progress(current_job_id, db_progress_val, progress_data['current_page'],
                                progress_data['total_pages'])
        except Exception as db_error:
            print(f"⚠️ Database progress update hatası: {db_error}")