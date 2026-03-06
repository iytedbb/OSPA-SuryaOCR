"""
Advanced PDF OCR Web Application Backend
FastAPI-based server with YOLO document processing capabilities
Filename: on_isleme_main.py
"""

from flask import Flask, Blueprint, request, jsonify, send_file, abort, render_template
from flask_cors import CORS

import os
import tempfile
import shutil
from pathlib import Path
import asyncio
from typing import List, Optional, Dict, Any
import json
import uuid
from datetime import datetime
import fitz  # pymupdf
import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
import torch
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import psutil
from io import BytesIO
import zipfile
import base64
import hashlib
from dataclasses import dataclass, asdict
import logging
import itertools

# Optional dependencies for HuggingFace Hub
try:
    from huggingface_hub import hf_hub_download
    HF_HUB_AVAILABLE = True
except ImportError:
    HF_HUB_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mevcut dosyanın bulunduğu dizin (app/modules/ocr/)
BACKEND_DIR = Path(__file__).parent.resolve()

# Projenin kök dizinine git (app/modules/ocr/ -> app/modules/ -> app/ -> ospa_suryaocr/)
PROJECT_ROOT = BACKEND_DIR.parent.parent.parent

# Kök dizindeki klasörleri hedefle
# Eski: app/database/veriler -> Yeni: data/veriler
UPLOAD_DIR = PROJECT_ROOT / "data" / "veriler" / "on_isleme" / "uploads"
OUTPUT_DIR = PROJECT_ROOT / "data" / "veriler" / "on_isleme" / "outputs"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Flask blueprint (ön işleme API’si)
preprocess_bp = Blueprint(
    "preprocess_bp",
    __name__
)

# Create directories
for directory in [UPLOAD_DIR, OUTPUT_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# CUDA Check
CUDA_AVAILABLE = torch.cuda.is_available()
if CUDA_AVAILABLE:
    logger.info(f"✓ CUDA available: {torch.cuda.get_device_name(0)}")
    logger.info(f"  VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
else:
    logger.info("✗ CUDA unavailable, using CPU mode")

# Import optional dependencies
try:
    from py_reform import straighten, save_pdf
    PY_REFORM_AVAILABLE = True
    logger.info("py-reform successfully imported")
except ImportError as e:
    PY_REFORM_AVAILABLE = False
    logger.warning(f"py-reform import error: {e}")

try:
    from doclayout_yolo import YOLOv10
    DOCLAYOUT_AVAILABLE = True
    logger.info("DocLayout-YOLO successfully imported")
except ImportError as e:
    DOCLAYOUT_AVAILABLE = False
    logger.warning(f"DocLayout-YOLO import error: {e}")

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
    logger.info("✅ SuryaOCR (new API) import OK")
except ImportError as e_new:
    logger.warning(f"⚠️ Yeni API import olmadı: {e_new}")
    try:
        # 🕰️ Eski API (run_ocr, batch_text_detection)
        from surya.ocr import run_ocr
        from surya.detection import batch_text_detection
        CODE_TO_LANGUAGE = None
        SURYA_AVAILABLE = True
        SURYA_API = "old"
        logger.info("✅ SuryaOCR (old API) import OK")
    except ImportError as e_old:
        logger.error(f"❌ SuryaOCR import hatası: {e_old}")
        logger.warning("SuryaOCR kullanılamayacak.")
        SURYA_AVAILABLE = False
        SURYA_API = None

@dataclass
class ProcessingSettings:
    """Processing configuration data structure"""
    # Image enhancement
    contrast: float = 1.0
    brightness: float = 1.2
    sharpness: float = 1.0
    saturation: float = 1.0

    # Threshold
    threshold_enable: bool = False
    threshold_value: int = 127
    threshold_type: str = "binary"

    # Morphology
    morphology_enable: bool = False
    morphology_operation: str = "opening"
    morphology_kernel_size: int = 3
    morphology_iterations: int = 1

    # Gaussian blur
    gaussian_enable: bool = False
    gaussian_kernel_size: int = 5
    gaussian_sigma: float = 1.0

    # Edge enhancement
    edge_enhance_enable: bool = False
    edge_enhance_factor: float = 1.5

    # Rotation
    rotation_angle: float = 0.0

    # Document enhancement
    py_reform_enable: bool = False
    py_reform_model: str = "uvdoc"

    # YOLO detection
    doclayout_enable: bool = True
    doclayout_device: str = "cuda" if CUDA_AVAILABLE else "cpu"

    # Output
    output_format: str = "pdf"
    output_dpi: int = 300
    enable_split: bool = True
    page_order: str = "sol-sag"  # "sol-sag" or "sag-sol"

class FastImageProcessor:
    """High-performance image processing engine"""

    @staticmethod
    def apply_all_processing_static(image: Image.Image, settings: Dict[str, Any]) -> Image.Image:
        """Apply all processing steps to an image"""
        try:
            if settings.get("auto_enhance", False):
                settings["contrast"] = 1.3
                settings["brightness"] = 1.2
                settings["sharpness"] = 1.3
                settings["edge_enhance_enable"] = True

            # Convert to numpy for CV2 operations
            img_array = np.array(image)

            # Color space conversion for CV2
            if len(img_array.shape) == 3:
                img_cv2 = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            else:
                img_cv2 = img_array

            # Convert to grayscale if enabled
            if settings.get("grayscale_enable", False):
                if len(img_cv2.shape) == 3:
                    img_cv2 = cv2.cvtColor(img_cv2, cv2.COLOR_BGR2GRAY)
                    logger.info("✅ ToGray: Görüntü siyah-beyaz tonlamaya dönüştürüldü.")

            # Apply thresholding
            if settings.get('threshold_enable', False):
                if len(img_cv2.shape) == 3:
                    img_cv2 = cv2.cvtColor(img_cv2, cv2.COLOR_BGR2GRAY)

                threshold_type = settings.get('threshold_type', 'binary')
                threshold_value = settings.get('threshold_value', 127)

                if threshold_type == "binary":
                    _, img_cv2 = cv2.threshold(img_cv2, threshold_value, 255, cv2.THRESH_BINARY)
                elif threshold_type == "adaptive_mean":
                    img_cv2 = cv2.adaptiveThreshold(
                        img_cv2, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 11, 2
                    )
                elif threshold_type == "adaptive_gaussian":
                    img_cv2 = cv2.adaptiveThreshold(
                        img_cv2, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
                    )

            # Apply morphological operations
            if settings.get('morphology_enable', False):
                kernel_size = settings.get('morphology_kernel_size', 3)
                iterations = settings.get('morphology_iterations', 1)
                operation = settings.get('morphology_operation', 'opening')

                kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))

                if operation == "opening":
                    img_cv2 = cv2.morphologyEx(img_cv2, cv2.MORPH_OPEN, kernel, iterations=iterations)
                elif operation == "closing":
                    img_cv2 = cv2.morphologyEx(img_cv2, cv2.MORPH_CLOSE, kernel, iterations=iterations)
                elif operation == "erosion":
                    img_cv2 = cv2.erode(img_cv2, kernel, iterations=iterations)
                elif operation == "dilation":
                    img_cv2 = cv2.dilate(img_cv2, kernel, iterations=iterations)

            # Apply Gaussian blur
            if settings.get('gaussian_enable', False):
                kernel_size = settings.get('gaussian_kernel_size', 5)
                sigma = settings.get('gaussian_sigma', 1.0)
                if kernel_size % 2 == 0:
                    kernel_size += 1
                img_cv2 = cv2.GaussianBlur(img_cv2, (kernel_size, kernel_size), sigma)

            # Convert back to PIL for PIL operations
            if len(img_cv2.shape) == 3:
                img_pil = Image.fromarray(cv2.cvtColor(img_cv2, cv2.COLOR_BGR2RGB))
            else:
                img_pil = Image.fromarray(img_cv2)

            # Apply PIL enhancements
            if settings.get('contrast', 1.0) != 1.0:
                enhancer = ImageEnhance.Contrast(img_pil)
                img_pil = enhancer.enhance(settings.get('contrast', 1.0))

            if settings.get('brightness', 1.0) != 1.0:
                enhancer = ImageEnhance.Brightness(img_pil)
                img_pil = enhancer.enhance(settings.get('brightness', 1.0))

            if settings.get('sharpness', 1.0) != 1.0:
                enhancer = ImageEnhance.Sharpness(img_pil)
                img_pil = enhancer.enhance(settings.get('sharpness', 1.0))

            if settings.get('saturation', 1.0) != 1.0:
                enhancer = ImageEnhance.Color(img_pil)
                img_pil = enhancer.enhance(settings.get('saturation', 1.0))

            # Apply edge enhancement
            if settings.get('edge_enhance_enable', False):
                factor = settings.get('edge_enhance_factor', 1.5)
                img_pil = img_pil.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))

            # Apply rotation
            rotation_angle = settings.get('rotation_angle', 0.0)
            if rotation_angle != 0.0:
                img_pil = img_pil.rotate(rotation_angle, expand=True, fillcolor='white')

            return img_pil

        except Exception as e:
            logger.error(f"Image processing error: {e}")
            return image

    @staticmethod
    def apply_py_reform_enhancement(image: Image.Image, model: str = "uvdoc", prefer_cuda: bool = True) -> Image.Image:
        """py-reform ile doküman düzeltme - metin koruyucu"""
        if not PY_REFORM_AVAILABLE:
            logger.warning("py-reform kütüphanesi yüklenmemiş, geçiliyor...")
            return image

        try:
            # Device selection
            device = "cuda" if (prefer_cuda and CUDA_AVAILABLE) else "cpu"

            logger.info(f"py-reform çalışıyor, device: {device}, model: {model}")

            temp_image = image

            # PIL Image'i geçici dosya olarak kaydet
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                temp_image.save(temp_file.name, 'PNG')
                temp_path = temp_file.name

            try:
                # py-reform ile doküman düzeltme uygula
                enhanced_result = straighten(temp_path, model="uvdoc", device=device)

                # Sonuç kontrolü
                if hasattr(enhanced_result, '__len__') and not isinstance(enhanced_result, (str, bytes)):
                    if len(enhanced_result) > 0:
                        enhanced_image = enhanced_result[0]
                    else:
                        logger.warning("py-reform: Boş liste döndü")
                        return image
                else:
                    enhanced_image = enhanced_result

                # PIL Image'e çevir
                if hasattr(enhanced_image, 'save'):
                    result_pil = enhanced_image
                elif isinstance(enhanced_image, np.ndarray):
                    if enhanced_image.dtype != np.uint8:
                        enhanced_image = (enhanced_image * 255).astype(np.uint8)
                    result_pil = Image.fromarray(enhanced_image)
                else:
                    logger.warning(f"py-reform: Beklenmeyen format: {type(enhanced_image)}")
                    return image

                logger.info("py-reform başarıyla uygulandı")
                return result_pil

            finally:
                try:
                    os.unlink(temp_path)
                except:
                    pass

        except Exception as e:
            logger.error(f"py-reform enhancement error: {e}")
            return image

class PageDetector:
    """DocLayout-YOLO ile sayfa tipi tespiti"""

    def __init__(self, device="cpu"):
        """
        Args:
            device: 'cuda' veya 'cpu'
        """
        self.model = None
        if device == "auto":
            self.device = "cuda" if CUDA_AVAILABLE else "cpu"
        else:
            self.device = device

        self.model_loaded = False
        self.surya_detector = None
        self.surya_loaded = False
        
        # 32GB VRAM için Batch Size ayarı
        self.batch_size = 32 

        if DOCLAYOUT_AVAILABLE:
            self.initialize_model()

    def initialize_model(self):
        """Model'i yükle ve GPU'ya sabitle"""
        if self.model_loaded and self.model is not None:
            return True

        try:
            model_loaded = False
            current_dir = Path(__file__).parent.resolve()
            app_root_dir = current_dir.parent.parent
            target_model_path = app_root_dir / "app" / "database" / "models" / "doclayout_yolo_docstructbench_imgsz1024.pt"

            local_model_paths = [
                target_model_path,
                current_dir / "doclayout_yolo_docstructbench_imgsz1024.pt",
            ]

            logger.info("🔍 Yerel YOLO model dosyası aranıyor...")
            for model_path in local_model_paths:
                resolved_path = model_path.resolve()
                if resolved_path.exists():
                    try:
                        self.model = YOLOv10(str(resolved_path))
                        logger.info(f"✓ YOLO model yerel dosyadan yüklendi: {resolved_path}")
                        model_loaded = True
                        break
                    except Exception as e:
                        logger.warning(f"Yerel model yüklenemedi: {e}")

            if not model_loaded and HF_HUB_AVAILABLE:
                try:
                    logger.info("☁️ Hugging Face Hub'dan YOLO modeli indirme deneniyor...")
                    weight_path = hf_hub_download(
                        repo_id="juliozhao/DocLayout-YOLO-DocStructBench",
                        filename="doclayout_yolo_docstructbench_imgsz1024.pt",
                    )
                    self.model = YOLOv10(weight_path)
                    model_loaded = True
                except Exception as e:
                    logger.warning(f"HuggingFace Hub hatası: {e}")

            if not model_loaded:
                try:
                    logger.info("🔄 Önceden eğitilmiş (pretrained) YOLO modeli deneniyor...")
                    self.model = YOLOv10.from_pretrained('juliensimon/doclayout-yolo-docstructbench')
                    model_loaded = True
                except Exception as e:
                    logger.warning(f"Pretrained model hatası: {e}")

            if not model_loaded:
                logger.error("❌ YOLO model yüklenemedi!")
                return False

            if hasattr(self.model, "to"):
                try:
                    target_device = self.device if self.device in ("cuda", "cpu") else "cpu"
                    self.model.to(target_device)
                    # Yarım hassasiyet (FP16) kullanımı performansı artırır (Ada GPU'larda)
                    if target_device == "cuda":
                         logger.info("🚀 Performance Mode: CUDA FP16 enabled implies faster inference.")
                    logger.info(f"🧠 YOLO modeli '{target_device}' cihazına taşındı.")
                except Exception as e_dev:
                    logger.warning(f"Cihaz taşıma hatası: {e_dev}")

            self.model_loaded = True
            return True

        except Exception as e:
            logger.error(f"DocLayout-YOLO model yükleme hatası: {e}", exc_info=True)
            return False

    # Tekil metodu (Geriye uyumluluk ve Preview endpointi için)
    def detect_page_type(self, image, page_num: int = 0):
        res_list = self.detect_page_type_batch([image], [page_num])
        return res_list[0]

    def detect_page_type_batch(self, images: List[Image.Image], page_nums: List[int]):
        """
        Birden fazla resmi aynı anda (Batch) işleyerek tahminleri döndürür.
        32GB VRAM avantajını burada kullanacağız.
        """
        batch_results = []
        
        # Görüntüleri CV2 formatına çevir (YOLO için)
        cv_images = [cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR) for img in images]

        try:
            # --- 1. YOLO Inference (Batch) ---
            # Tek seferde N adet resmi GPU'ya gönderiyoruz
            yolo_results = []
            if DOCLAYOUT_AVAILABLE and self.model_loaded:
                yolo_results = self.model.predict(
                    cv_images,
                    imgsz=1024,
                    conf=0.25,
                    device=self.device,
                    verbose=False,
                    stream=False # List olarak dönmesi için False
                )

            # --- 2. Surya Inference (Gerekirse) ---
            surya_boxes_map = {} # {index: boxes}
            
            # Sadece ilk 5 sayfa için Surya kontrolü yapılacaksa filtrele
            indices_needing_surya = [i for i, p_num in enumerate(page_nums) if p_num < 5]
            
            if SURYA_AVAILABLE and indices_needing_surya:
                if not self.surya_loaded:
                    self.initialize_surya_model()
                
                surya_images = [images[i] for i in indices_needing_surya]
                
                try:
                    if SURYA_API == "new" and self.surya_detector:
                        preds = self.surya_detector(surya_images) # Batch inference
                        for idx, pred in zip(indices_needing_surya, preds):
                            if pred.bboxes:
                                surya_boxes_map[idx] = np.array([b.bbox for b in pred.bboxes])
                    
                    elif SURYA_API == "old" and self.surya_detector:
                        results = self.surya_detector(surya_images, device=self.device)
                        for idx, res in zip(indices_needing_surya, results):
                            if res is not None:
                                surya_boxes_map[idx] = res
                except Exception as e:
                    logger.warning(f"Surya batch hatası: {e}")

            # --- 3. Sonuçları Birleştir ve Sınıflandır ---
            for i, image in enumerate(images):
                page_num = page_nums[i]
                
                # Surya sonucu var mı?
                external_boxes = surya_boxes_map.get(i)
                
                # YOLO sonucu var mı?
                yolo_res = [yolo_results[i]] if (yolo_results and i < len(yolo_results)) else None
                
                # Karar mekanizması
                # Eğer Surya sonucu varsa ve geçerliyse onu kullan, yoksa YOLO sonucunu kullan
                if external_boxes is not None and len(external_boxes) > 0:
                     # Surya ile analiz
                     res = self._classify_layout_results(None, image, external_boxes=external_boxes)
                elif yolo_res:
                     # YOLO ile analiz
                     res = self._classify_layout_results(yolo_res, image, external_boxes=None)
                else:
                     # Fallback
                     res = self._fallback_detection(image)
                
                batch_results.append(res)

            return batch_results

        except Exception as e:
            logger.error(f"Batch detection hatası: {e}", exc_info=True)
            # Hata durumunda her resim için fallback döndür
            return [self._fallback_detection(img) for img in images]

    def _classify_layout_results(self, results, image, external_boxes=None):
        """YOLO sonuçlarını veya harici kutuları sınıflandır"""
        try:
            aspect_ratio = image.width / image.height
            is_landscape = aspect_ratio > 1.25

            # --- YENİ KUTU ÇIKARMA MANTIĞI ---
            boxes = None
            is_surya_source = False  # <-- YENİ SATIR

            if external_boxes is not None:
                # DURUM 1: Surya'dan (veya dışarıdan) gelen kutular (Filtreleme yok)
                boxes = external_boxes
                is_surya_source = True  # <-- YENİ SATIR
                logger.debug(f"Using {len(boxes)} boxes from external source (Surya)")

            elif results and len(results) > 0 and hasattr(results[0], 'boxes') and results[0].boxes is not None:
                # DURUM 2: YOLO'dan gelen kutular (Filtreleme GEREKLİ)
                try:
                    all_boxes = results[0].boxes.xyxy
                    class_ids = results[0].boxes.cls.cpu().numpy().astype(int)
                    confs = results[0].boxes.conf.cpu().numpy()
                    names = self.model.model.names

                    filtered_boxes = []
                    for i, box in enumerate(all_boxes):
                        conf = confs[i]
                        # Güven filtresi
                        if conf < 0.35:
                            continue

                        label = names[class_ids[i]]
                        # Sınıf filtresi
                        if label in ("plain text", "title", "figure_caption"):
                            filtered_boxes.append(box)

                    logger.debug(f"Total YOLO boxes={len(all_boxes)}, Filtered text/conf boxes={len(filtered_boxes)}")

                    if len(filtered_boxes) > 0:
                        cpu_boxes = []
                        for box in filtered_boxes:
                            if hasattr(box, 'cpu'):
                                cpu_boxes.append(box.cpu().numpy())
                            elif isinstance(box, np.ndarray):
                                cpu_boxes.append(box)
                            else:
                                cpu_boxes.append(np.array(box))
                        boxes = np.array(cpu_boxes)
                    else:
                        boxes = None
                        logger.debug("No text boxes after YOLO filtering")

                except Exception as e:
                    logger.error(f"Box processing error: {e}")
                    boxes = None

            # --- YENİ GAZETE TESPİTİ (GazeteOCRProcessor.py'dan UYARLANDI) ---
            content_type = 'standard'
            is_newspaper_flag = False
            width, height = image.size

            # 1. Sayfa boyutu filtresi (çok küçükse gazete değildir)
            if height < 1500 or width < 1000:
                logger.info(f"📰 Gazete tespiti: HAYIR (Sayfa boyutu küçük: {width}x{height})")

            # 2. Yeterli layout elementi var mı? (GÜNCELLENDİ)
            # Surya (çok kutu = ~150+) ve YOLO (az kutu = ~15+) için farklı eşikler
            min_box_threshold = 150 if is_surya_source else 15
            logger.debug(
                f"   📊 Gazete box eşiği: {min_box_threshold} (Kaynak: {'Surya' if is_surya_source else 'YOLO'})")

            if boxes is None or len(boxes) < min_box_threshold:
                box_count = 0 if boxes is None else len(boxes)
                logger.info(f"📰 Gazete tespiti: HAYIR (Element sayısı: {box_count}, Eşik: {min_box_threshold})")

            else:
                # 3. Kolon Tespiti (X-merkezlerine göre - GazeteProcessor mantığı)
                try:
                    # X merkezlerini al
                    x_positions = []
                    for box in boxes:
                        x_center = (box[0] + box[2]) / 2
                        x_positions.append(x_center)

                    x_positions.sort()

                    # Ardışık elementler arası boşluğu hesapla
                    gaps = []
                    for i in range(len(x_positions) - 1):
                        gap = x_positions[i + 1] - x_positions[i]
                        gaps.append(gap)

                    if not gaps:
                        logger.info("📰 Gazete tespiti: HAYIR (Boşluk tespiti yapılamadı)")

                    else:
                        # Ortalama boşluk
                        avg_gap = np.mean(gaps)

                        # Büyük boşluklar (kolon ayraçları) say
                        # GazeteProcessor'daki dinamik eşik: avg_gap * 2.5
                        column_threshold = avg_gap * 2.5
                        large_gaps = [g for g in gaps if g > column_threshold]
                        column_count = len(large_gaps) + 1

                        logger.info(f"   📊 Tespit edilen kolon sayısı (dinamik): {column_count}")

                        # 4. Karar Aşaması
                        # Gazete için en az 3 kolon GEREKLİ (GazeteProcessor'daki threshold=3)
                        if column_count < 3:
                            logger.info(f"📰 Gazete tespiti: HAYIR ({column_count} kolon, eşik 3)")

                        # Ek filtre: Düşük çözünürlüklü/küçük sayfalarda 3 kolon da yeterli değil
                        elif height < 2500 and column_count <= 3:
                            logger.info(f"📰 Gazete tespiti: HAYIR (Belge yüksekliği düşük ({height}px) ve kolon <= 3)")

                        else:
                            # 3+ kolon ve yeterli yoğunluk (yukarıda <15 ile elendi)
                            is_newspaper_flag = True
                            logger.info(f"📰 GAZETE TESPİT EDİLDİ! ({column_count} kolon)")

                except Exception as e_gap:
                    logger.error(f"Gazete (gap) tespiti sırasında hata: {e_gap}")
                    is_newspaper_flag = False  # Hata olursa gazete varsayma

            if is_newspaper_flag:
                content_type = 'newspaper'
            # --- YENİ GAZETE TESPİTİ SONU ---

            # === ESKİ MANTIK BLOKU (DEĞİŞMEDİ) ===

            # Box'lar varsa (yani metin bulunduysa) analiz et
            if boxes is not None and len(boxes) > 0:
                text_columns = self._detect_text_columns(boxes, image.width)
                num_columns = len(text_columns)
                logger.debug(f"Analyzing {len(boxes)} text boxes, detected {num_columns} columns")

                if is_landscape:
                    # DURUM 1: Geniş sayfa ve 2+ metin sütunu (Normal çift sayfa)
                    if num_columns >= 2:
                        split_pos = self._calculate_optimal_split(text_columns, image.width, boxes)
                        logger.debug(f"Returning 'double' (2+ text columns), split: {split_pos}")
                        # 3 DEĞER DÖNDÜR
                        return "double", split_pos, content_type

                    # DURUM 2: Geniş sayfa ve SADECE 1 metin sütunu (Boş sayfa sorunu)
                    elif num_columns == 1:
                        split_pos_center = image.width // 2  # Merkeze geri dön
                        split_pos = self._adjust_split_to_avoid_boxes(split_pos_center, boxes, image.width)
                        logger.debug(f"Returning 'double' (1 text column fallback), split: {split_pos}")
                        # 3 DEĞER DÖNDÜR
                        return "double", split_pos, content_type
                else:
                    # DURUM 4: Portre sayfa (Geniş değil)
                    logger.debug("Returning 'single' (Portrait with text)")
                    # 3 DEĞER DÖNDÜR
                    return "single", None, content_type

            # === MANTIK BLOKU SONU ===

            # Box yoksa VEYA (Durum 3'teki gibi) metin sütunu bulunamadıysa:
            logger.debug("No text columns found, using projection/aspect fallback")
            split_by_proj = self._projection_split_guess(image)

            if is_landscape and split_by_proj is not None:
                logger.debug(f"Returning 'double' (Projection fallback), split: {split_by_proj}")
                # 3 DEĞER DÖNDÜR
                return "double", split_by_proj, content_type

            # Son çare: Sadece aspect ratio'ya göre karar ver
            logger.debug("Returning result from aspect ratio analysis")
            # _analyze_by_aspect_ratio'yu çağır (o da 3 değer döndürecek)
            page_type, split_pos, _ = self._analyze_by_aspect_ratio(image)
            return page_type, split_pos, content_type  # content_type'ı buradan ekle

        except Exception as e:
            logger.error(f"Layout classification error: {e}")
            page_type, split_pos, _ = self._analyze_by_aspect_ratio(image)
            # Hata durumunda da 3 değer döndür
            return page_type, split_pos, 'standard'

    def initialize_surya_model(self):
        """Surya Detection modelini yükle"""
        if self.surya_loaded or not SURYA_AVAILABLE:
            return True
        try:
            target_device = self.device if self.device in ("cuda", "cpu") else "cpu"
            if SURYA_API == "new":
                logger.info(f"Surya (New API) yükleniyor, device: {target_device}")
                self.surya_detector = DetectionPredictor(device=target_device)
            elif SURYA_API == "old":
                logger.info(f"Surya (Old API) yükleniyor, device: {target_device}")
                self.surya_detector = batch_text_detection
            self.surya_loaded = True
            return True
        except Exception as e:
            logger.error(f"Surya model hatası: {e}", exc_info=True)
            return False

    def _projection_split_guess(self, image):
        """Dikey projeksiyon ile bölme noktası bul"""
        try:
            cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
            binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                           cv2.THRESH_BINARY, 31, 15)

            # Dikey projeksiyon - siyah piksel sayısı
            proj = np.sum(binary == 0, axis=0).astype(np.float32)

            # Kenarları at (%10 buffer)
            w = image.width
            left = int(w * 0.1)
            right = int(w * 0.9)
            if right - left < 50:
                return None

            window = proj[left:right]
            if window.size == 0:
                return None

            # En az içerikli nokta (vadi)
            min_idx = int(np.argmin(window))
            split_x = left + min_idx

            return split_x
        except Exception:
            return None

    def _detect_text_columns(self, boxes, image_width):
        """Text kolonlarını tespit et"""
        if len(boxes) == 0:
            return []

        # X merkezlerini al
        x_centers = [(box[0] + box[2]) / 2 for box in boxes]

        # Cluster'lama
        sorted_x = sorted(x_centers)
        columns = []
        current_cluster = []

        for x in sorted_x:
            if not current_cluster or abs(x - np.mean(current_cluster)) < image_width * 0.15:
                current_cluster.append(x)
            else:
                if current_cluster:
                    columns.append(np.mean(current_cluster))
                current_cluster = [x]

        if current_cluster:
            columns.append(np.mean(current_cluster))

        # Kenarlara çok yakın olanları filtrele
        edge_margin = image_width * 0.1
        filtered_columns = [col for col in columns if edge_margin < col < image_width - edge_margin]

        return filtered_columns

    def _calculate_optimal_split(self, text_columns, image_width, yolo_boxes):
        """Optimal bölme noktasını hesapla"""
        if len(text_columns) >= 2:
            # En büyük boşluğu bul
            gaps = []
            for i in range(len(text_columns) - 1):
                gap_center = (text_columns[i] + text_columns[i + 1]) / 2
                gap_size = text_columns[i + 1] - text_columns[i]
                gaps.append((gap_center, gap_size))

            # Merkeze en yakın ve büyük olan boşluğu seç
            center_x = image_width / 2
            best_gap = min(gaps, key=lambda g: abs(g[0] - center_x) - g[1] * 0.5)
            split_x = int(best_gap[0])
        else:
            split_x = image_width // 2

        # Box'lardan kaçın
        if yolo_boxes is not None and len(yolo_boxes) > 0:
            split_x = self._adjust_split_to_avoid_boxes(split_x, yolo_boxes, image_width)

        return split_x

    def _adjust_split_to_avoid_boxes(self, split_x, boxes, image_width, buffer=15, min_margin=28):
        """Split çizgisini box'lardan uzak tut"""

        def intersects(x, box, buf):
            x1, y1, x2, y2 = box
            return (x >= x1 - buf) and (x <= x2 + buf)

        if len(boxes) == 0:
            # CAST 1: Girdi ne olursa olsun int döndür
            return int(split_x)

        # Her box'un kenarından en az min_margin uzakta tut
        for box in boxes:
            x1, _, x2, _ = box

            # Sağ kenara çok yakınsa sağa kaydır
            if 0 < (split_x - x2) < min_margin:
                split_x = x2 + min_margin  # Bu noktada 'split_x' float olabilir

            # Sol kenara çok yakınsa sola kaydır
            elif 0 < (x1 - split_x) < min_margin:
                split_x = x1 - min_margin  # Bu noktada 'split_x' float olabilir

        # Hala box içine düşüyorsa boşluk ara
        if any(intersects(split_x, b, buffer) for b in boxes):
            max_shift = int(image_width * 0.25)
            step = 5
            for delta in range(step, max_shift, step):
                left_x = split_x - delta
                right_x = split_x + delta

                left_clear = all(
                    (left_x < x1 - min_margin or left_x > x2 + min_margin)
                    for x1, _, x2, _ in boxes
                )
                right_clear = all(
                    (right_x < x1 - min_margin or right_x > x2 + min_margin)
                    for x1, _, x2, _ in boxes
                )

                if left_clear:
                    # CAST 2: Geri dönen değeri int'e zorla
                    return int(left_x)
                if right_clear:
                    # CAST 3: Geri dönen değeri int'e zorla
                    return int(right_x)

        # CAST 4: Nihai geri dönüş değerini int'e zorla
        return int(split_x)

    def _fallback_detection(self, image):
        """Fallback: aspect ratio + projeksiyon"""
        aspect_ratio = image.width / image.height

        # Projeksiyon ile bölme noktası ara
        split_pos = self._projection_split_guess(image)

        # 1. Çift sayfa (Geniş, Landscape)
        if aspect_ratio > 1.4 and split_pos is not None:
            logger.debug("Fallback: 'double' (Projection split)")
            return ("double", split_pos, "standard")
        elif aspect_ratio > 1.3:
            logger.debug("Fallback: 'double' (Aspect ratio center split)")
            return ("double", image.width // 2, "standard")

        # 2. Döndürülmüş Çift Sayfa (Çok Dar, Tall)

        elif aspect_ratio < 0.5:
            logger.debug("Fallback: 'rotated_double' (Very tall aspect ratio)")
            return ("rotated_double", None, "standard")

        # 3. Tek Sayfa (Portre)
        else:
            logger.debug("Fallback: 'single' (Portrait aspect ratio)")
            return ("single", None, "standard")

    def _analyze_by_aspect_ratio(self, image):
        """Basit aspect ratio analizi - DÜZELTME: Tek portre sayfaları doğru tespit et"""
        aspect_ratio = image.width / image.height

        # Projection ile çift sayfa kontrolü
        split_pos = self._projection_split_guess(image)

        # 1. Çift sayfa tespiti - sadece yatay (landscape) sayfalar
        if aspect_ratio > 1.4 and split_pos is not None:
            logger.debug("Analyze Aspect: 'double' (Projection split)")
            return ("double", split_pos, "standard")
        elif aspect_ratio > 1.3:
            logger.debug("Analyze Aspect: 'double' (Aspect ratio center split)")
            return ("double", image.width // 2, "standard")

        # 2. Döndürülmüş Çift Sayfa (Çok Dar, Tall)
        elif aspect_ratio < 0.5:
            logger.debug("Analyze Aspect: 'rotated_double' (Very tall aspect ratio)")
            return ("rotated_double", None, "standard")

        # 3. Tek Sayfa (Portre)
        else:
            logger.debug("Analyze Aspect: 'single' (Portrait aspect ratio)")
            return ("single", None, "standard")

# Global instances
page_detector = None

def get_page_detector():
    """Get or create page detector instance"""
    global page_detector
    if page_detector is None:
        device = "cuda" if CUDA_AVAILABLE else "cpu"
        page_detector = PageDetector(device=device)
    return page_detector

# Job management
active_jobs = {}
job_results = {}

@preprocess_bp.route("/", methods=["GET"])
def serve_preprocessing_app():
    """Ön işleme arayüzünü (on_isleme_index.html) sunar."""
    try:
        # templates klasöründeki on_isleme_index.html'i render et
        return render_template('on_isleme_index.html')
    except Exception as e:
        logger.error(f"Ön işleme arayüzü render hatası: {e}", exc_info=True)
        # Hata durumunda basit bir hata sayfası veya mesajı döndür
        return f"<h1>Hata</h1><p>Ön işleme arayüzü yüklenemedi: {e}</p>", 500

@preprocess_bp.route("/api/status", methods=["GET"])
def get_status():
    """Get system status"""
    return jsonify({
        "status": "online",
        "cuda_available": CUDA_AVAILABLE,
        "py_reform_available": PY_REFORM_AVAILABLE,
        "doclayout_available": DOCLAYOUT_AVAILABLE,
        "cpu_count": mp.cpu_count(),
        "memory_info": {
                "total": psutil.virtual_memory().total,
                "available": psutil.virtual_memory().available,
                "percent": psutil.virtual_memory().percent
        }
    }), 200

@preprocess_bp.route("/api/upload", methods=["POST"])
def upload_file():
    """Upload PDF/Image file for processing"""
    file = request.files.get("file")
    if file is None or file.filename == "":
        abort(400, description="Dosya yüklenmedi")

    supported_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.tif']
    file_extension = '.' + file.filename.lower().split('.')[-1]

    if file_extension not in supported_extensions:
        abort(400, description="Desteklenen formatlar: PDF, JPG, PNG, TIFF")

    try:
        # Generate unique job ID
        job_id = str(uuid.uuid4())

        # Save uploaded file
        file_path = UPLOAD_DIR / f"{job_id}_{file.filename}"
        file.save(str(file_path))

        # Extract basic info
        if file_extension == '.pdf':
            doc = fitz.open(str(file_path))
            page_count = len(doc)
            doc.close()
        else:
            page_count = 1  # image treated as single page

        # Store job info (global sözlükler korunuyor)
        active_jobs[job_id] = {
            "filename": file.filename,
            "file_path": str(file_path),
            "page_count": page_count,
            "file_type": file_extension,
            "status": "uploaded",
            "created_at": datetime.now().isoformat(),
            "completed_pages": 0
        }

        return jsonify({
            "job_id": job_id,
            "filename": file.filename,
            "page_count": page_count,
            "file_type": file_extension,
            "message": "Dosya başarıyla yüklendi",
            "file_path": str(file_path)

        }), 200

    except Exception as e:
        logger.error(f"Upload error: {e}")
        abort(500, description=f"Yükleme başarısız: {str(e)}")


@preprocess_bp.route("/api/job/<job_id>/preview/<int:page_num>", methods=["GET"])
def get_page_preview(job_id: str, page_num: int):
    """Get page preview as base64 image AND run YOLO detection."""
    if job_id not in active_jobs:
        abort(404, description="Job not found")

    try:
        job_info = active_jobs[job_id]
        file_path = Path(job_info["file_path"])
        file_type = job_info["file_type"]
        page_count = job_info["page_count"]

        if page_num < 0 or page_num >= page_count:
            abort(400, description="Geçersiz sayfa numarası")

        # --- GÖRÜNTÜ YÜKLEME VE PIL DÖNÜŞÜMÜ ---
        pil_image = None
        if file_type == ".pdf":
            doc = fitz.open(str(file_path))
            page = doc[page_num]
            # 150-200 DPI preview uygundur
            zoom = 2.0
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)  # RGB (alpha=False)

            img_bytes = pix.samples

            # Ham RGB byte'larından PIL Image oluştur
            pil_image = Image.frombytes("RGB", [pix.width, pix.height], img_bytes)
            doc.close()
        else:
            # Görüntü dosyası (JPG, PNG, TIFF)
            pil_image = Image.open(str(file_path))
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')

        # --- YOLO TESPİTİ ---
        logger.info(f"Running YOLO detection for preview: Job {job_id}, Page {page_num}")
        detector = get_page_detector()
        # YENİ: 3. değeri (content_type) al, _ (alt çizgi) ile görmezden gel
        page_type, split_position, _content_type = detector.detect_page_type(pil_image, page_num=page_num)
        logger.info(f"YOLO Result: {page_type}, Split: {split_position}, Content: {_content_type}")


        # --- PIL Görüntüsünü Base64'e çevir ---
        buf = BytesIO()
        pil_image.save(buf, format="PNG")  # Ön uca göndermek için PNG olarak sıkıştır
        img_bytes_for_b64 = buf.getvalue()
        b64_str = base64.b64encode(img_bytes_for_b64).decode("utf-8")
        # --- Base64 SONU ---

        # Yanıta 'page_type' ve 'split_position' eklendi
        return jsonify({
            "job_id": job_id,
            "page_num": page_num,
            "image": "data:image/png;base64," + b64_str,
            "page_type": page_type,
            "split_position": split_position,
            "content_type": _content_type
        }), 200

    except Exception as e:
        # Hata mesajını daha detaylı logla
        logger.error(f"Page preview error: {e}", exc_info=True)
        abort(500, description=f"Önizleme oluşturulamadı: {e}")


@preprocess_bp.route("/api/process", methods=["POST"])
# Fonksiyon parametrelerinden job_id'yi kaldır
def process_document():
    """Start document processing (Flask version)"""
    try:
        # JSON gövdesinden ayarları ve dosya yolunu al
        data = request.get_json(force=True)
        settings = data.get("settings")
        file_path_str = data.get("file_path") # file_path'i body'den al

        if not file_path_str:
             abort(400, description="file_path required in request body")
        if not isinstance(settings, dict):
            abort(400, description="Invalid settings format in request body")

        # --- YENİ: Dosya yolundan yeni bir iş oluştur ---
        # Bu endpoint her çağrıldığında yeni bir ön işleme işi başlatıyoruz
        job_id = str(uuid.uuid4()) # Yeni, benzersiz bir ID oluştur
        file_path = Path(file_path_str)
        filename = file_path.name
        file_extension = file_path.suffix.lower()

        # Sayfa sayısını tekrar kontrol et (özellikle PDF için)
        page_count = 1
        if file_extension == '.pdf':
            try:
                # PDF dosyasını açıp sayfa sayısını almayı dene
                # UPLOAD_DIR veya başka bir yerde olabilir, tam yolu kullan
                doc = fitz.open(str(file_path))
                page_count = len(doc)
                doc.close()
            except Exception as e:
                 logger.warning(f"Could not get page count for {filename} at {file_path}: {e}")
                 page_count = 1 # Hata olursa 1 sayfa varsay

        # active_jobs sözlüğüne yeni işi ekle
        active_jobs[job_id] = {
            "filename": filename,
            "file_path": str(file_path), # Tam dosya yolunu sakla
            "page_count": page_count,
            "file_type": file_extension,
            "status": "processing", # Doğrudan işleme durumunda başlat
            "created_at": datetime.now().isoformat(),
            "completed_pages": 0,
            "settings": settings # Ayarları işle birlikte sakla
        }
        logger.info(f"✨ New preprocessing job created: {job_id} for file {filename}")

        # --- Flask'te background işlem başlat ---
        import threading
        thread = threading.Thread(
            # process_document_background fonksiyonuna YENİ oluşturulan job_id'yi gönder
            target=process_document_background, args=(job_id, settings)
        )
        thread.daemon = True
        thread.start()

        logger.info(f"📄 Background preprocessing started for NEW job {job_id}")

        # Frontend'e oluşturulan YENİ job_id'yi döndür
        return jsonify({"message": "Processing started", "job_id": job_id}), 200

    except Exception as e:
        logger.error(f"Processing error in /api/process: {e}", exc_info=True) # Hatanın detayını logla
        # Hata durumunda JSON döndür, abort etme
        return jsonify({"error": f"Processing could not be started: {str(e)}"}), 500

def _process_pages_sync(job_id: str, file_path: str, file_type: str, total_pages: int, settings: Dict[str, Any]) -> List[Image.Image]:
    """
    Synchronous worker function that processes all pages of a document.
    This function is designed to be run in a separate thread via `run_in_executor`.
    It contains the heavy, blocking loop but can safely update the shared `active_jobs`
    dictionary to report real-time progress without freezing the main server.
    """
    page_times_seconds = []
    processed_images = []
    detector = get_page_detector()

    doc = fitz.open(file_path) if file_type == ".pdf" else None

    for page_num in range(total_pages):
        page_start_time = datetime.now()

        # Initial progress update for the current page
        active_jobs[job_id]["completed_pages"] = page_num
        active_jobs[job_id]["current_page"] = page_num + 1

        try:
            # --- 1. Load Page Image ---
            if doc:
                page = doc[page_num]
                dpi = settings.get('output_dpi', 300)
                mat = fitz.Matrix(dpi / 72, dpi / 72)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                pil_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            else:  # For single image files
                pil_image = Image.open(file_path).convert("RGB")

            # --- 2. Detect Layout and Apply Pre-processing ---
            page_type, split_position, content_type = detector.detect_page_type(pil_image, page_num=page_num)

            # YENİ: Gazete tespiti mantığı
            is_newspaper_page = (page_type == "double") or (content_type == 'newspaper')

            should_split = (settings.get('enable_split', True) and is_newspaper_page and split_position is not None)

            # YENİ: py-reform mantığı (auto_enhance kontrolü)
            is_auto_enhance = settings.get("auto_enhance", False)

            # 1. Ayarı manuel olarak al
            run_py_reform = settings.get("py_reform_enable", False)

            # 2. Öncelik 1: "Otomatik Ayarlar" açıksa kapat
            if is_auto_enhance:
                run_py_reform = False
                logger.info(f"Sayfa {page_num + 1}: Otomatik ayar açık. py-reform atlanıyor.")

            # 3. Öncelik 2: Gazete ise (ve hala açıksa) kapat
            elif is_newspaper_page and run_py_reform:
                run_py_reform = False
                logger.info(
                    f"Sayfa {page_num + 1}: Gazete tipi algılandı (type: {page_type}, content: {content_type}). py-reform atlanıyor.")

            # Apply document-level enhancements like py-reform before splitting/processing
            if run_py_reform:  # <-- 'run_py_reform' bayrağını kullan
                pil_image = FastImageProcessor.apply_py_reform_enhancement(pil_image)

            # --- 3. Process Page(s) ---
            if should_split:
                left_half = pil_image.crop((0, 0, split_position, pil_image.height))
                right_half = pil_image.crop((split_position, 0, pil_image.width, pil_image.height))

                left_processed = FastImageProcessor.apply_all_processing_static(left_half, settings)
                right_processed = FastImageProcessor.apply_all_processing_static(right_half, settings)

                if settings.get('page_order', 'sol-sag') == "sag-sol":
                    processed_images.extend([right_processed, left_processed])
                else:
                    processed_images.extend([left_processed, right_processed])
            else:
                processed_image = FastImageProcessor.apply_all_processing_static(pil_image, settings)
                processed_images.append(processed_image)

            # --- 4. Calculate Timings and Update Global Job Status ---
            page_duration_seconds = (datetime.now() - page_start_time).total_seconds()
            page_times_seconds.append(page_duration_seconds)

            avg_time_per_page = sum(page_times_seconds) / len(page_times_seconds)
            remaining_pages = total_pages - (page_num + 1)
            estimated_remaining = avg_time_per_page * remaining_pages

            # This update to the shared dictionary is thread-safe for this use case
            # and is what the /status endpoint will read.
            active_jobs[job_id].update({
                "avg_page_time": avg_time_per_page,
                "last_page_time": page_duration_seconds,
                "estimated_remaining": estimated_remaining
            })

            logger.info(
                f"Job {job_id}: Page {page_num + 1}/{total_pages} processed in {page_duration_seconds:.2f}s. ETA: {estimated_remaining:.0f}s")

        except Exception as e:
            logger.error(f"Failed to process page {page_num + 1} for job {job_id}: {e}", exc_info=True)
            continue  # Skip corrupted/problematic pages

    if doc:
        doc.close()

    # Final progress update after loop finishes
    active_jobs[job_id]["completed_pages"] = total_pages
    return processed_images


def process_document_background(job_id: str, settings: Dict[str, Any]):
    """Belgeyi arka planda işle - SAYFA SAYFA ilerleme güncellemesi ile"""
    try:
        job_info = active_jobs[job_id]
        file_path = Path(job_info["file_path"])
        file_type = job_info["file_type"]
        total_pages = job_info["page_count"]
        base_name = Path(job_info["filename"]).stem
        output_dir = OUTPUT_DIR / job_id
        output_dir.mkdir(exist_ok=True)

        start_time = datetime.now()
        processed_page_paths = []
        detector = get_page_detector()

        output_format = settings.get("output_format", "pdf").lower()
        dpi = settings.get("output_dpi", 300)

        doc = fitz.open(file_path) if file_type == ".pdf" else None

        # Sayfa sayfa işle - her sayfa sonrası UI güncellenir
        for page_num in range(total_pages):
            page_start_time = datetime.now()
            
            # İlerlemeyi güncelle (sayfa işleme başladı)
            active_jobs[job_id]["current_page"] = page_num + 1
            
            try:
                # 1. Sayfayı yükle (PDF -> PIL Image)
                if doc:
                    page = doc[page_num]
                    mat = fitz.Matrix(dpi / 72, dpi / 72)
                    pix = page.get_pixmap(matrix=mat, alpha=False)
                    pil_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                else:
                    pil_image = Image.open(file_path).convert("RGB")
                
                # 2. YOLO Detection (GPU) - tek sayfa
                page_type, split_position, content_type = detector.detect_page_type(pil_image, page_num=page_num)
                
                # 3. Sayfa işleme (CPU)
                result_paths = _process_single_page_logic(
                    pil_image,
                    page_num,
                    settings,
                    page_type,
                    split_position,
                    content_type,
                    output_dir,
                    output_format,
                    dpi
                )
                processed_page_paths.extend(result_paths)
                
            except Exception as e:
                logger.error(f"Error processing page {page_num + 1}: {e}")
            
            # Her sayfa BİTTİĞİNDE completed_pages'i bir artır
            active_jobs[job_id]["completed_pages"] = page_num + 1
            
            # Sayfa bazlı anında zaman ve ETA güncellemesi
            elapsed = (datetime.now() - start_time).total_seconds()
            page_time = (datetime.now() - page_start_time).total_seconds()
            pages_done = page_num + 1
            
            avg_time = elapsed / pages_done
            remaining = avg_time * (total_pages - pages_done)
            
            active_jobs[job_id].update({
                "avg_page_time": avg_time,
                "last_page_time": page_time,
                "estimated_remaining": remaining
            })
            
            logger.info(f"📄 Sayfa {pages_done}/{total_pages} tamamlandı ({page_time:.1f}s, kalan: {remaining:.0f}s)")

        if doc:
            doc.close()

        # 4. Sonuçları Birleştirme (Merge) - Aynı mantık
        # Sıralama önemli: processed_page_paths listesini dosya adına göre sırala
        # Çünkü executor karışık sırada bitirebilir
        processed_page_paths.sort(key=lambda p: str(p))

        if output_format == "pdf":
            final_output_path = output_dir / f"{base_name}_OSPA_onisleme_processed.pdf"
            merged_doc = fitz.open()
            for pdf_path in processed_page_paths:
                try:
                    with fitz.open(pdf_path) as temp_doc:
                        merged_doc.insert_pdf(temp_doc)
                except Exception as e:
                    logger.warning(f"Merge skipped for {pdf_path}: {e}")
            merged_doc.save(final_output_path)
            merged_doc.close()
            # Geçici dosyaları sil
            for temp_pdf in processed_page_paths:
                try: os.unlink(temp_pdf)
                except: pass

        elif output_format == "tiff" and len(processed_page_paths) > 1:
            final_output_path = output_dir / f"{base_name}_OSPA_onisleme_processed.tiff"
            images = [Image.open(p).convert("RGB") for p in processed_page_paths]
            first, rest = images[0], images[1:]
            first.save(final_output_path, save_all=True, append_images=rest, compression="lzw")
            for p in processed_page_paths:
                try: os.unlink(p)
                except: pass
        else:
            final_output_path = output_dir / f"{base_name}_OSPA_onisleme_processed_{output_format.upper()}"
            if len(processed_page_paths) == 1:
                final_output_path = processed_page_paths[0]
            else:
                zip_path = str(final_output_path) + ".zip"
                import zipfile
                with zipfile.ZipFile(zip_path, 'w') as zf:
                    for img_path in processed_page_paths:
                        zf.write(img_path, img_path.name)
                final_output_path = Path(zip_path)

        # 5. Final job results
        total_duration = (datetime.now() - start_time).total_seconds()
        job_results[job_id] = {
            "status": "completed",
            "output_file": str(final_output_path),
            "total_pages": total_pages,
            "total_processed_pages": len(processed_page_paths),
            "processing_time": total_duration,
            "completed_at": datetime.now().isoformat(),
            "settings_used": settings,
            "original_filename": job_info["filename"],
            "redirect_to_ocr": True
        }

        active_jobs[job_id]["status"] = "completed"
        active_jobs[job_id]["estimated_remaining"] = 0
        logger.info(f"🎉 Job {job_id} completed. Final file: {final_output_path}")

    except Exception as e:
        logger.error(f"Critical error in background preprocessing for job {job_id}: {e}", exc_info=True)
        active_jobs[job_id]["status"] = "failed"
        job_results[job_id] = {
            "status": "failed",
            "error": str(e)
        }

def _process_single_page_logic(pil_image, page_num, settings, page_type, split_position, content_type, output_dir, output_format, dpi):
    """
    Tek bir sayfanın CPU üzerindeki görüntü işleme (enhancement, crop) ve kaydetme mantığı.
    Bu fonksiyon ThreadPoolExecutor içinde çalışır.
    """
    processed_paths = []
    
    # py-reform / auto-enhance mantığı
    is_newspaper_page = (content_type == 'newspaper')
    is_auto_enhance = settings.get("auto_enhance", False)
    run_py_reform = settings.get("py_reform_enable", False)

    if run_py_reform and is_auto_enhance:
        run_py_reform = False
    elif run_py_reform and is_newspaper_page:
        run_py_reform = False

    # Enhancement
    if run_py_reform:
        # py-reform GPU'da çalışacak şekilde güncellendi
        pil_image = FastImageProcessor.apply_py_reform_enhancement(pil_image, model=settings.get("py_reform_model", "uvdoc"), prefer_cuda=True)
    
    # Split Check
    should_split_check = (page_type == "double") or (content_type == 'newspaper')
    should_split = (settings.get("enable_split", True) and should_split_check and split_position is not None)

    processed_images = []
    if should_split:
        left_half = pil_image.crop((0, 0, split_position, pil_image.height))
        right_half = pil_image.crop((split_position, 0, pil_image.width, pil_image.height))
        left_processed = FastImageProcessor.apply_all_processing_static(left_half, settings)
        right_processed = FastImageProcessor.apply_all_processing_static(right_half, settings)
        
        if settings.get("page_order", "sol-sag") == "sag-sol":
            processed_images = [right_processed, left_processed]
        else:
            processed_images = [left_processed, right_processed]
    else:
        processed_images = [FastImageProcessor.apply_all_processing_static(pil_image, settings)]

    # Save
    for idx, img in enumerate(processed_images):
        img_rgb = img.convert("RGB")
        # Sayfa numaralandırmasını düzgün yap (page_1_1, page_1_2 gibi)
        page_suffix = f"page_{page_num + 1:04d}_{idx + 1}" # 04d sıralama için önemli

        if output_format == "pdf":
            temp_path = output_dir / f"{page_suffix}.pdf"
            img_rgb.save(temp_path, "PDF", resolution=dpi)
            processed_paths.append(temp_path)
        elif output_format in ["png", "jpg", "jpeg"]:
            temp_path = output_dir / f"{page_suffix}.{output_format}"
            save_kwargs = {"dpi": (dpi, dpi)}
            if output_format in ["jpg", "jpeg"]: save_kwargs["quality"] = 95
            img_rgb.save(temp_path, output_format.upper(), **save_kwargs)
            processed_paths.append(temp_path)
        elif output_format == "tiff":
            temp_path = output_dir / f"{page_suffix}.tiff"
            img_rgb.save(temp_path, "TIFF", dpi=(dpi, dpi), compression="lzw")
            processed_paths.append(temp_path)
            
    return processed_paths

async def create_merged_output(
        processed_images: List[Image.Image],
        output_dir: Path,
        base_name: str,
        output_format: str,
        settings: Dict[str, Any]
) -> Path:
    """Create a merged output file from processed images"""
    try:
        output_format = output_format.lower()
        dpi = settings.get('output_dpi', 300)

        # --- DEĞİŞİKLİK BAŞLANGICI: Çok sayfalı PNG/JPG'yi PDF'ye zorla ---
        original_output_format = output_format

        # Eğer format PDF veya TIFF değilse (yani PNG/JPG ise) VE birden fazla resim varsa:
        if output_format not in ['pdf', 'tiff'] and len(processed_images) > 1:
            logger.warning(
                f"Multiple '{output_format.upper()}' output selected for {len(processed_images)} pages. "
                f"Forcing PDF creation instead of ZIP."
            )
            # Çıktı formatını 'pdf' olarak zorla
            output_format = 'pdf'
        # --- DEĞİŞİKLİK SONU ---

        # Çıktı dosya adını ve yolunu (güncellenmiş formata göre) oluştur
        output_filename = f"{base_name}_processed.{output_format}"
        output_path = output_dir / output_filename

        if output_format == 'pdf':
            # Create merged PDF
            pdf_doc = fitz.open()

            for i, img in enumerate(processed_images):
                # Convert PIL image to bytes
                img_buffer = BytesIO()
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                img.save(img_buffer, format='PNG', dpi=(dpi, dpi))
                img_bytes = img_buffer.getvalue()

                # Create new PDF page
                img_doc = fitz.open("png", img_bytes)
                page = img_doc[0]

                # Calculate page size based on DPI
                page_width = img.width * 72 / dpi
                page_height = img.height * 72 / dpi

                # Create new page in output PDF
                new_page = pdf_doc.new_page(width=page_width, height=page_height)

                # Insert image
                rect = fitz.Rect(0, 0, page_width, page_height)
                new_page.insert_image(rect, stream=img_bytes)

                img_doc.close()

                logger.info(f"Added page {i + 1}/{len(processed_images)} to PDF")

            # Save merged PDF
            pdf_doc.save(str(output_path))
            pdf_doc.close()

            # Orijinal format PNG/JPG ise (yani PDF'ye zorladıysak) log mesajı ekle
            if original_output_format != 'pdf':
                logger.info(f"✅ Created merged PDF (forced from {original_output_format.upper()}): {output_path}")
            else:
                logger.info(f"✅ Created merged PDF: {output_path} ({len(processed_images)} pages)")

        elif output_format in ['png', 'jpg', 'jpeg', 'tiff']:
            # Bu blok artık SADECE 1 resim varsa VEYA format TIFF ise çalışacak

            if len(processed_images) == 1:
                # Single image - save directly
                img = processed_images[0]
                if output_format in ['jpg', 'jpeg'] and img.mode != 'RGB':
                    img = img.convert('RGB')

                save_kwargs = {'dpi': (dpi, dpi)}
                if output_format in ['jpg', 'jpeg']:
                    save_kwargs['quality'] = 95

                img.save(str(output_path), format=output_format.upper(), **save_kwargs)
                logger.info(f"✅ Saved single image: {output_path}")

            else:
                # Multiple images - SADECE TIFF buraya düşmeli
                if output_format == 'tiff':
                    # Multi-page TIFF
                    if processed_images:
                        first_img = processed_images[0]
                        if first_img.mode != 'RGB':
                            first_img = first_img.convert('RGB')

                        # Convert other images
                        other_images = []
                        for img in processed_images[1:]:
                            if img.mode != 'RGB':
                                img = img.convert('RGB')
                            other_images.append(img)

                        # Save multi-page TIFF
                        first_img.save(
                            str(output_path),
                            format='TIFF',
                            save_all=True,
                            append_images=other_images,
                            dpi=(dpi, dpi),
                            compression='lzw'
                        )
                        logger.info(f"✅ Created multi-page TIFF: {output_path} ({len(processed_images)} pages)")

                # --- ESKİ ZIP OLUŞTURMA BLOĞU ARTIK GEREKLİ DEĞİL ---

        return output_path

    except Exception as e:
        logger.error(f"Merge output error: {e}")
        # Fallback - save as individual files
        fallback_files = []
        for i, img in enumerate(processed_images):
            fallback_filename = f"{base_name}_page_{i + 1:03d}.png"
            fallback_path = output_dir / fallback_filename
            img.save(str(fallback_path), format='PNG', dpi=(dpi, dpi))
            fallback_files.append(fallback_path)

        logger.warning(f"Used fallback - saved {len(fallback_files)} individual PNG files")
        return fallback_files[0] if fallback_files else output_dir / "error.txt"

def save_temp_pdf(image: Image.Image, page_num: int, output_dir: Path, dpi: int = 300) -> Path:
    """Tek bir sayfa görselini geçici PDF olarak kaydet"""
    temp_pdf_path = output_dir / f"page_{page_num+1}.pdf"
    if image.mode != "RGB":
        image = image.convert("RGB")
    image.save(temp_pdf_path, "PDF", resolution=dpi)
    return temp_pdf_path


def process_single_page_worker(page_data_dict):
    """Worker function for parallel page processing"""
    try:
        from PIL import Image
        from io import BytesIO
        import os

        # Extract parameters
        image_bytes = page_data_dict['image_bytes']
        page_num = page_data_dict['page_num']
        settings = page_data_dict['settings']
        dpi = page_data_dict['dpi']
        should_split = page_data_dict['should_split']
        split_position = page_data_dict['split_position']
        output_dir = page_data_dict['output_dir']
        base_name = page_data_dict['base_name']
        output_format = page_data_dict['output_format']
        page_order = page_data_dict.get('page_order', 'sol-sag')

        # YENİ: content_type'ın worker'a gelmesi GEREKİR.
        # Eğer gelmezse, 'should_split'e göre tahmin et (eski hatalı mantık)
        # TODO: Bu worker'ı çağıran koda 'content_type' eklenmeli
        content_type = page_data_dict.get('content_type', 'standard')
        if content_type == 'standard' and should_split:
            # Eski kodla uyumluluk için, eğer split varsa gazete varsay
            is_newspaper_page = True
        else:
            is_newspaper_page = (content_type == 'newspaper')

        # Load image
        full_image = Image.open(BytesIO(image_bytes))

        # --- DÜZELTİLMİŞ PY-REFORM MANTIĞI (WORKER İÇİN) ---
        # HATA DÜZELTMESİ: py-reform mantığı split bloğunun DIŞINA taşındı

        is_auto_enhance = settings.get("auto_enhance", False)
        run_py_reform = settings.get("py_reform_enable", False)

        if run_py_reform and is_auto_enhance:
            run_py_reform = False
        elif run_py_reform and is_newspaper_page:
            run_py_reform = False

        # Apply py-reform if enabled (YENİ BAYRAK KULLAN)
        if run_py_reform:
            try:
                full_image = FastImageProcessor.apply_py_reform_enhancement(
                    full_image,
                    model=settings.get('py_reform_model', 'uvdoc'),
                    prefer_cuda=True  # GPU aktif
                )
            except Exception as e:
                # Worker'da loglama stdout'u kirletir, logger.warning daha iyi
                pass
                # --- DÜZELTME SONU ---

        # Double page processing
        if should_split and split_position is not None:

            # Split
            left_half = full_image.crop((0, 0, split_position, full_image.height))
            right_half = full_image.crop((split_position, 0, full_image.width, full_image.height))

            # Process both halves
            left_processed = FastImageProcessor.apply_all_processing_static(left_half, settings)
            right_processed = FastImageProcessor.apply_all_processing_static(right_half, settings)

            # Determine file order based on page_order
            if page_order == "sag-sol":
                # Ottoman: Right page first (2-1 order)
                first_image = right_processed
                second_image = left_processed
                first_suffix = "right"
                second_suffix = "left"
            else:
                # Latin: Left page first (1-2 order) - Default
                first_image = left_processed
                second_image = right_processed
                first_suffix = "left"
                second_suffix = "right"

            # Save files
            ext = output_format.lower()
            format_folder = os.path.join(output_dir, f"{ext.upper()}_Outputs")
            os.makedirs(format_folder, exist_ok=True)

            first_filename = f"{base_name}_page_{page_num + 1:03d}_{first_suffix}.{ext}"
            second_filename = f"{base_name}_page_{page_num + 1:03d}_{second_suffix}.{ext}"

            first_path = os.path.join(format_folder, first_filename)
            second_path = os.path.join(format_folder, second_filename)

            # Save with proper format
            if ext == "jpg":
                if first_image.mode != 'RGB':
                    first_image = first_image.convert('RGB')
                if second_image.mode != 'RGB':
                    second_image = second_image.convert('RGB')
                first_image.save(first_path, "JPEG", quality=95, dpi=(dpi, dpi))
                second_image.save(second_path, "JPEG", quality=95, dpi=(dpi, dpi))
            else:  # PNG or PDF
                first_image.save(first_path, ext.upper(), dpi=(dpi, dpi))
                second_image.save(second_path, ext.upper(), dpi=(dpi, dpi))

            return (page_num, 'split', [first_path, second_path])

        else:
            # Single page processing
            # py-reform zaten yukarıda (split dışında) uygulandı
            processed_image = FastImageProcessor.apply_all_processing_static(full_image, settings)

            # Save file
            ext = output_format.lower()
            format_folder = os.path.join(output_dir, f"{ext.upper()}_Outputs")
            os.makedirs(format_folder, exist_ok=True)

            filename = f"{base_name}_page_{page_num + 1:03d}.{ext}"
            file_path = os.path.join(format_folder, filename)

            if ext == "jpg":
                if processed_image.mode != 'RGB':
                    processed_image = processed_image.convert('RGB')
                processed_image.save(file_path, "JPEG", quality=95, dpi=(dpi, dpi))
            else:
                processed_image.save(file_path, ext.upper(), dpi=(dpi, dpi))

            return (page_num, 'single', [file_path])

    except Exception as e:
        # logger.error(f"Worker {page_num + 1} error: {e}") # Loglama worker'da sorunlu
        return (page_num, 'error', str(e))
@preprocess_bp.route("/api/job/preview_from_path", methods=["POST"])
def get_page_preview_from_path():
    """Get page preview as base64 image AND run YOLO detection, using file path."""
    data = request.get_json(force=True)
    file_path_str = data.get("file_path")
    page_num = int(data.get("page_num", 0))

    if not file_path_str:
        abort(400, description="file_path required")

    file_path = Path(file_path_str)
    if not file_path.exists():
         # Try resolving relative to project root if absolute path fails
         file_path_rel = PROJECT_ROOT / file_path_str # PROJECT_ROOT should be defined at top
         if not file_path_rel.exists():
              abort(404, description=f"File not found at {file_path_str} or {file_path_rel}")
         file_path = file_path_rel # Use the resolved relative path


    file_type = file_path.suffix.lower()

    if file_type not in ['.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.tif']:
         abort(400, description="Unsupported file type for preview")

    try:
        # --- GÖRÜNTÜ YÜKLEME VE PIL DÖNÜŞÜMÜ ---
        pil_image = None
        page_count = 1
        if file_type == ".pdf":
            doc = fitz.open(str(file_path))
            page_count = len(doc)
            if page_num < 0 or page_num >= page_count:
                doc.close()
                abort(400, description="Invalid page number for PDF")

            page = doc[page_num]
            zoom = 2.0  # Preview resolution
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            pil_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            doc.close()
        else:
            # Görüntü dosyası
            pil_image = Image.open(str(file_path))
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')
            page_count = 1 # Image file always has 1 page in this context
            if page_num != 0:
                 abort(400, description="Invalid page number for image file (must be 0)")


        if not pil_image:
             abort(500, description="Failed to load image from file")

        # --- YOLO TESPİTİ ---
        logger.info(f"Running YOLO detection for preview from path: {file_path}, Page {page_num}")
        detector = get_page_detector()
        # YENİ: 3. değeri (content_type) al, _ (alt çizgi) ile görmezden gel
        page_type, split_position, _content_type = detector.detect_page_type(pil_image, page_num=page_num)
        logger.info(f"YOLO Result: {page_type}, Split: {split_position}, Content: {_content_type}")

        # --- PIL Görüntüsünü Base64'e çevir ---
        buf = BytesIO()
        pil_image.save(buf, format="PNG")
        b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")

        # Yanıta 'page_type', 'split_position', and 'page_count' ekle
        return jsonify({
            "image": "data:image/png;base64," + b64_str,
            "page_type": page_type,
            "split_position": split_position,
            "page_count": page_count, # Send total page count back
            "content_type": _content_type
        }), 200

    except Exception as e:
        logger.error(f"Page preview from path error: {e}", exc_info=True)
        abort(500, description=f"Preview generation failed: {e}")

@preprocess_bp.route("/api/job/<job_id>/processed_preview", methods=["GET"])
def get_processed_preview(job_id: str):
    """Get the first processed page preview image (Flask version)"""
    if job_id not in job_results or job_results[job_id].get("status") != "completed":
        abort(404, description="Job results not found or not completed")

    result_info = job_results[job_id]
    preview_path = result_info.get("first_page_preview")

    if not preview_path or not os.path.exists(preview_path):
        abort(404, description="Processed preview image not found")

    try:
        logger.info(f"🖼️ Serving processed preview for job {job_id}")
        return send_file(
            preview_path,
            mimetype='image/jpeg',
            as_attachment=False  # tarayıcıda gösterilsin, indirilmesin
        )
    except Exception as e:
        logger.error(f"Processed preview error: {e}")
        abort(500, description=f"Önizleme sunulamadı: {str(e)}")

@preprocess_bp.route("/api/job/<job_id>/processed_page/<int:page_num>", methods=["GET"])
def get_processed_page_preview(job_id: str, page_num: int):
    """
    Get a specific page preview from the FINAL PROCESSED file (PDF, TIFF, or ZIP). (Flask version)
    """
    if job_id not in job_results or job_results[job_id].get("status") != "completed":
        abort(404, description="Job results not found or not completed")

    result_info = job_results[job_id]
    output_file_path = result_info.get("output_file")

    if not output_file_path or not os.path.exists(output_file_path):
        abort(404, description="Processed output file not found")

    file_extension = Path(output_file_path).suffix.lower()

    try:
        pil_image = None

        if file_extension == '.pdf':
            # Handle PDF
            doc = fitz.open(output_file_path)
            if page_num >= len(doc):
                doc.close()
                abort(400, description="Page number out of range")

            page = doc[page_num]
            mat = fitz.Matrix(2.0, 2.0)  # yüksek çözünürlük
            pix = page.get_pixmap(matrix=mat, alpha=False)
            pil_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            doc.close()

        elif file_extension == '.tiff':
            # Handle multi-page TIFF
            tiff_image = Image.open(output_file_path)
            try:
                tiff_image.seek(page_num)
                pil_image = tiff_image.copy()
                if pil_image.mode != 'RGB':
                    pil_image = pil_image.convert('RGB')
            except EOFError:
                abort(400, description="Page number out of range for TIFF")
            finally:
                tiff_image.close()

        elif file_extension == '.zip':
            # YENİ EKLENDİ: Handle ZIP file containing images
            try:
                with zipfile.ZipFile(output_file_path, 'r') as zf:
                    # Get file list and sort it (to ensure page 1, 2, 3 order)
                    # Ignore metadata files like __MACOSX or .DS_Store
                    file_list = sorted(
                        [f for f in zf.namelist() if
                         not f.startswith('__MACOSX') and not f.endswith('.DS_Store') and f.endswith(('.png', '.jpg', '.jpeg'))]
                    )

                    if page_num >= len(file_list):
                        abort(400, description="Page number out of range for ZIP")

                    image_filename = file_list[page_num]
                    with zf.open(image_filename) as image_file:
                        # Read file into BytesIO buffer to be opened by PIL
                        image_data = BytesIO(image_file.read())
                        pil_image = Image.open(image_data)
                        if pil_image.mode != 'RGB':
                            pil_image = pil_image.convert('RGB')
            except zipfile.BadZipFile:
                 abort(500, description="Processed ZIP file is corrupted")
            except Exception as e_zip:
                 logger.error(f"Error reading from ZIP file: {e_zip}")
                 abort(500, description="Failed to read image from ZIP")

        else:
            # Handle single images (PNG, JPG)
            if page_num == 0 and file_extension in ['.png', '.jpg', '.jpeg']:
                pil_image = Image.open(output_file_path)
                if pil_image.mode != 'RGB':
                    pil_image = pil_image.convert('RGB')
            else:
                abort(400, description="Navigation not supported for this output format or page number")

        if pil_image:
            img_buffer = BytesIO()
            pil_image.save(img_buffer, format='PNG')
            img_data = img_buffer.getvalue()
            img_base64 = base64.b64encode(img_data).decode()

            return jsonify({
                "image": f"data:image/png;base64,{img_base64}",
                "page_type": "processed",
                "split_position": None,
                "width": pil_image.width,
                "height": pil_image.height
            }), 200

        abort(500, description="Failed to load processed page")

    except Exception as e:
        logger.error(f"Processed page preview error: {e}", exc_info=True)
        abort(500, description=f"İşlenmiş sayfa yüklenemedi: {str(e)}")

@preprocess_bp.route("/api/job/<job_id>/status", methods=["GET"])
def get_job_status(job_id: str):
    """Get detailed job processing status with real-time progress and timing (Flask version)"""
    if job_id not in active_jobs:
        abort(404, description="Job not found")

    try:
        job_info = active_jobs[job_id]
        result_info = job_results.get(job_id, {})

        total_pages = job_info.get("page_count", 0)
        completed_pages = job_info.get("completed_pages", 0)
        current_page = job_info.get("current_page", 0)
        status = job_info.get("status", "pending") # Get current status from active_jobs

        # If the job is marked completed in results, use that status definitively
        if result_info.get("status") in ["completed", "failed"]:
            status = result_info["status"]

        # --- YENİ GÜNCELLEME: Tamamlanmış işler için sayfa sayılarını düzelt ---
        if status == "completed":
            # Navigasyon için işlenmiş sayfa sayısını kullan
            total_pages = result_info.get("total_processed_pages", total_pages)
            completed_pages = total_pages
            # İşlenmiş belgeyi 1. sayfadan (veya 0. indeksten) başlat
            current_page = 1 if total_pages > 0 else 0
        elif status == "processing":
             # current_page zaten active_jobs'tan geliyor
             pass
        else: # pending, failed, vb.
            current_page = 0
        # --- GÜNCELLEME SONU ---

        # --- İlerleme yüzdesi ---
        if total_pages > 0 and status == "processing": # Only show >0% if actually processing
            progress = round((completed_pages / total_pages) * 100, 2)
        elif status == "completed":
            progress = 100
        else:
            progress = 0

        # --- Zaman hesaplamaları ---
        estimated_remaining = job_info.get("estimated_remaining", 0) if status == "processing" else 0
        last_page_time = job_info.get("last_page_time", 0)
        avg_page_time = job_info.get("avg_page_time", 0)

        # Kalan süreyi okunabilir metin haline getir
        def format_time(seconds: float) -> str:
            seconds = int(seconds) # Convert to integer seconds
            if seconds <= 0: return "Tamamlanıyor..." if status=="processing" else "0 saniye"
            if seconds < 60: return f"{seconds} saniye"
            elif seconds < 3600: return f"{seconds // 60} dakika {seconds % 60} saniye"
            else:
                hours = seconds // 3600
                minutes = (seconds % 3600) // 60
                return f"{hours} saat {minutes} dakika"

        estimated_remaining_text = format_time(estimated_remaining)

        # Dakikadaki sayfa hızı
        pages_per_minute = 0
        if avg_page_time > 0:
            pages_per_minute = round(60 / avg_page_time, 2)

        # --- YENİ GÜNCELLEME: Sonuç (result) objesine daha fazla veri ekle ---
        response_data = {
            "status": status,
            "progress": progress,
            "current_page": current_page, # Artık tamamlandığında 1 olacak
            "page_count": total_pages, # Artık tamamlandığında işlenmiş sayfa sayısı olacak
            "completed_pages": completed_pages,
            "timing": {
                "estimated_remaining": estimated_remaining,
                "estimated_remaining_text": estimated_remaining_text,
                "last_page_time": round(last_page_time, 2),
                "avg_page_time": round(avg_page_time, 2),
                "pages_per_minute": pages_per_minute,
            },
            "result": { # Frontend'in sağ panelde göstermesi için tüm veriler
                 "output_file": result_info.get("output_file"),
                 "error": result_info.get("error"),
                 "settings_used": result_info.get("settings_used"),
                 "processing_time": result_info.get("processing_time"),
                 "total_processed_pages": result_info.get("total_processed_pages"),
                 "original_filename": result_info.get("original_filename")
            },
            # --- GÜNCELLEME SONU ---
            "redirect_to_ocr": result_info.get("redirect_to_ocr", False)
        }

        return jsonify(response_data), 200

    except Exception as e:
        logger.error(f"Job status error: {e}")
        abort(500, description=f"Job status retrieval failed: {str(e)}")

@preprocess_bp.route("/api/job/<job_id>/download", methods=["GET"])
def download_results(job_id: str):
    """Download processed results as single merged file (Flask version)"""
    if job_id not in job_results:
        abort(404, description="Results not found")

    result_info = job_results[job_id]
    if result_info.get("status") != "completed":
        abort(400, description="Processing not completed")

    try:
        output_file_path = result_info.get("output_file")
        if not output_file_path or not os.path.exists(output_file_path):
            abort(404, description="Output file not found")

        # Determine media type based on file extension
        file_extension = Path(output_file_path).suffix.lower()
        media_types = {
            '.pdf': 'application/pdf',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.tiff': 'image/tiff',
            '.zip': 'application/zip'
        }
        media_type = media_types.get(file_extension, 'application/octet-stream')

        # Generate download filename
        job_info = active_jobs.get(job_id, {})
        original_name = Path(job_info.get("filename", "document")).stem
        download_filename = f"{original_name}_processed{file_extension}"

        logger.info(f"📦 Download request: {download_filename}")

        # Flask'te dosya indirme
        return send_file(
            output_file_path,
            as_attachment=True,
            download_name=download_filename,
            mimetype=media_type
        )

    except Exception as e:
        logger.error(f"Download error: {e}")
        abort(500, description=f"Download failed: {str(e)}")

# --- YENİ EKLENTI: Arka Planda Modelleri Isıt (Warmup) ---
import threading
def _warmup_models_bg():
    try:
        logger.info(" Arka planda ön işleme modelleri çağrılıyor...")
        get_page_detector()
        logger.info("✅ Ön işleme modelleri (YOLO) ısındı ve belleğe alındı!")
    except Exception as e:
        logger.warning(f"Modeller ısıtılamadı: {e}")

threading.Thread(target=_warmup_models_bg, daemon=True).start()
