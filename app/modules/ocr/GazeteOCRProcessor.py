"""
Gazete OCR İşleme Modülü - GPU Optimized
Backend'den bağımsız, tam işlevsel sınıf
UPDATED: Surya Layout desteği eklendi
FIXED: Surya position-based reading order (kolon mantığı bypass)
"""

from typing import List, Dict, Any, Tuple, Optional
from PIL import Image
import numpy as np
import re
import torch


class GazeteOCRProcessor:
    """
    YOLO + SuryaOCR ile gazete işleme sınıfı - GPU Accelerated
    - Gazete tespiti (YOLO - GPU)
    - Layout analizi (YOLO veya Surya - GPU)
    - OCR (SuryaOCR - GPU)
    - Kolon bazlı sıralama (sadece YOLO için)
    - Başlık/paragraf ayırımı
    
    UPDATED: layout_engine parametresi ile Surya veya YOLO seçilebilir
    FIXED: Surya seçildiğinde position attribute'u kullanılır, kolon mantığı bypass edilir
    """

    def __init__(self, yolo_model_path: str, recognizer, detector, 
                 layout_predictor=None, layout_engine: str = "yolo"):
        """
        Args:
            yolo_model_path: YOLO model dosyası yolu
            recognizer: SuryaOCR RecognitionPredictor (GPU'da)
            detector: SuryaOCR DetectionPredictor (GPU'da)
            layout_predictor: SuryaOCR LayoutPredictor (GPU'da) - opsiyonel
            layout_engine: "yolo" veya "surya" - hangi layout motoru kullanılacak
        """
        self.recognizer = recognizer
        self.detector = detector
        self.layout_predictor = layout_predictor
        self.layout_engine = layout_engine.lower()

        # GPU device'ı belirle
        self.device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
        print(f"Gazete Processor Device: {self.device}")
        print(f"Layout Engine: {self.layout_engine.upper()}")

        # YOLO modelini yükle ve GPU'ya taşı
        try:
            from doclayout_yolo import YOLOv10

            # Model'i yükle
            self.yolo_model = YOLOv10(model=yolo_model_path, task="detect")

            # YOLO'yu GPU'ya taşı
            if torch.cuda.is_available():
                try:
                    # Model'in içindeki PyTorch model'e eriş ve GPU'ya taşı
                    if hasattr(self.yolo_model, 'model'):
                        self.yolo_model.model = self.yolo_model.model.to(self.device)
                        print(f"YOLO model GPU'ya tasindi: {self.device}")
                    else:
                        print(f"YOLO model GPU'ya tasinamadi (model attribute yok)")
                except Exception as gpu_error:
                    print(f"YOLO GPU transfer hatasi: {gpu_error}")
                    print(f"   YOLO CPU'da calisacak")
            else:
                print(f"CUDA kullanilamiyor, YOLO CPU'da calisacak")

            self.yolo_available = True
            print(f"YOLO model yuklendi: {yolo_model_path}")

            # GPU bellek durumu
            if torch.cuda.is_available():
                allocated = torch.cuda.memory_allocated() / 1e6
                cached = torch.cuda.memory_reserved() / 1e6
                print(f"GPU Bellek - Allocated: {allocated:.1f}MB, Cached: {cached:.1f}MB")

        except Exception as e:
            print(f"YOLO yuklenemedi: {e}")
            self.yolo_model = None
            self.yolo_available = False

        # Surya Layout kontrolü
        self.surya_layout_available = self.layout_predictor is not None
        if self.surya_layout_available:
            print(f"Surya Layout kullanilabilir")
        else:
            print(f"Surya Layout kullanilamiyor")
            if self.layout_engine == "surya":
                print(f"   layout_engine='surya' ama LayoutPredictor yok, YOLO'ya geciliyor")
                self.layout_engine = "yolo"

    def set_layout_engine(self, engine: str):
        """Layout motorunu değiştir (runtime'da)"""
        engine = engine.lower()
        if engine == "surya" and not self.surya_layout_available:
            print(f"Surya Layout kullanilamiyor, YOLO kalacak")
            return False
        if engine == "yolo" and not self.yolo_available:
            print(f"YOLO kullanilamiyor, Surya kalacak")
            return False
        
        self.layout_engine = engine
        print(f"Layout engine degistirildi: {engine.upper()}")
        return True

    def is_newspaper(self, images: List[Image.Image], threshold: int = 3) -> bool:
        """
        Görsel(ler) gazete mi tespit et - GPU Accelerated (iyileştirilmiş)
        Ek filtreler:
          - Sayfa boyutu (yükseklik/genişlik)
          - Metin yoğunluğu
          - Dinamik kolon eşiği
        """
        if not self.yolo_available or not images:
            return False

        print("Gazete tespiti yapiliyor... (GPU)")

        # İlk sayfayı analiz et (genelde yeterli)
        test_image = images[0]
        width, height = test_image.size

        # Sayfa boyutu filtresi (kitap/tezleri ele)
        if height < 1500 or width < 1000:
            print(f"   Sayfa boyutu kucuk ({width}x{height}), gazete degil")
            return False

        try:
            # YOLO prediction (GPU'da çalışacak)
            results = self.yolo_model.predict(test_image, verbose=False)
            boxes = results[0].boxes
            names = self.yolo_model.model.names

            if not boxes or len(boxes) == 0:
                print("   Layout elementi tespit edilemedi")
                return False

            # X koordinatlarını topla
            x_positions = []
            for box in boxes:
                conf = float(box.conf)
                if conf < 0.35:  # Düşük güvenli atla
                    continue

                xyxy = box.xyxy[0].tolist()
                x_center = (xyxy[0] + xyxy[2]) / 2
                x_positions.append(x_center)

            # Çok az element varsa gazete değildir
            if len(x_positions) < 15:
                print(f"   Cok az element ({len(x_positions)}), normal dokuman")
                return False

            # Kolonları tespit et
            x_positions.sort()

            # Ardışık elementler arası boşluğu hesapla
            gaps = []
            for i in range(len(x_positions) - 1):
                gap = x_positions[i + 1] - x_positions[i]
                gaps.append(gap)

            if not gaps:
                print("   Bosluk tespiti yapilamadi")
                return False

            # Ortalama boşluk
            avg_gap = sum(gaps) / len(gaps)

            # Büyük boşluklar (kolon ayraçları) say
            column_threshold = avg_gap * 2.5
            large_gaps = [g for g in gaps if g > column_threshold]
            column_count = len(large_gaps) + 1

            print(f"   Tespit edilen kolon sayisi: {column_count}")

            # Ek filtreler: sayfa uzunluğu ve kolon sayısı kombinasyonu
            if column_count < threshold:
                print(f"   Normal dokuman ({column_count} kolon, esik {threshold})")
                return False

            if height < 2500 and column_count <= 3:
                print(f"   Belge yuksekligi dusuk ({height}px), gazete degil")
                return False

            # 3+ kolon ve yeterli yoğunluk varsa gazete say
            is_newspaper = column_count >= threshold

            if is_newspaper:
                print(f"   GAZETE TESPIT EDILDI! ({column_count} kolon)")
            else:
                print(f"   Normal dokuman ({column_count} kolon)")

            return is_newspaper

        except Exception as e:
            print(f"   Tespit hatasi: {e}")
            return False

    def process_gazete_page(self, image: Image.Image) -> Dict[str, Any]:
        """
        Gazete sayfasını işle - tam pipeline (GPU Accelerated)
        MODIFIED: Gelişmiş bellek yönetimi ve OOM koruması eklendi.
        UPDATED: Surya veya YOLO layout seçilebilir.

        Returns:
            {
                'layout_elements': [...],
                'ocr_lines': [...],
                'paragraphs': [...],
                'statistics': {...}
            }
        """
        import gc

        original_size = image.size
        print(f"Gazete sayfasi isleniyor ({original_size})... (GPU)")
        print(f"   Layout Engine: {self.layout_engine.upper()}")

        # --- GPU BELLEK YONETIMI: Sayfa oncesi guvenli temizlik ---
        if torch.cuda.is_available():
            try:
                gc.collect()
                torch.cuda.empty_cache()
                torch.cuda.synchronize()

                # Bellek durumunu kontrol et
                memory_allocated = torch.cuda.memory_allocated() / (1024 ** 3)
                memory_total = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
                memory_free = memory_total - memory_allocated

                print(f"   GPU Bellek: {memory_allocated:.2f}GB kullanimda, {memory_free:.2f}GB bos")

                # Bellek kritik seviyedeyse agresif temizlik
                if memory_free < 2.0:
                    print(f"   Dusuk GPU bellegi! Agresif temizlik yapiliyor...")
                    gc.collect()
                    torch.cuda.empty_cache()
                    torch.cuda.synchronize()

            except Exception as mem_error:
                print(f"   Bellek kontrolu hatasi: {mem_error}")

        # --- GORUNTU BOYUTU KONTROLU ---
        max_dimension = 3000
        max_pixels = 9_000_000

        current_pixels = original_size[0] * original_size[1]
        processed_image = image
        scale_factor = 1.0

        if current_pixels > max_pixels or max(original_size) > max_dimension:
            scale_by_pixels = (max_pixels / current_pixels) ** 0.5
            scale_by_dimension = max_dimension / max(original_size)
            scale_factor = min(scale_by_pixels, scale_by_dimension, 1.0)

            new_width = int(original_size[0] * scale_factor)
            new_height = int(original_size[1] * scale_factor)

            print(f"   Goruntu kucultuluyor: {original_size} -> ({new_width}, {new_height})")
            processed_image = image.resize((new_width, new_height), Image.LANCZOS)

        layout_elements = []
        ocr_lines = []

        try:
            # 1. Layout Analizi (Surya veya YOLO)
            if self.layout_engine == "surya" and self.surya_layout_available:
                layout_elements = self._surya_layout_analysis(processed_image)
            else:
                layout_elements = self._yolo_layout_analysis(processed_image)

            # Ara temizlik
            if torch.cuda.is_available():
                try:
                    torch.cuda.empty_cache()
                except:
                    pass

            # 2. SuryaOCR (GPU) - Korumalı çağrı
            ocr_lines = self._surya_ocr_safe(processed_image)

            # 3. Bbox'ları orijinal boyuta ölçekle (eğer küçültme yapıldıysa)
            if scale_factor < 1.0:
                inv_scale = 1.0 / scale_factor

                for elem in layout_elements:
                    bbox = elem['bbox']
                    elem['bbox'] = [
                        int(bbox[0] * inv_scale),
                        int(bbox[1] * inv_scale),
                        int(bbox[2] * inv_scale),
                        int(bbox[3] * inv_scale)
                    ]

                for line in ocr_lines:
                    bbox = line['bbox']
                    line['bbox'] = [
                        bbox[0] * inv_scale,
                        bbox[1] * inv_scale,
                        bbox[2] * inv_scale,
                        bbox[3] * inv_scale
                    ]

            # 4. Eşleştirme
            element_to_lines = self._match_ocr_to_layout(ocr_lines, layout_elements)

            # 5. Okuma sırası (Surya: position-based, YOLO: kolon-based)
            reading_order = self._create_reading_order(layout_elements)

            # 6. Paragraf oluşturma
            paragraphs = self._create_paragraphs(reading_order, element_to_lines, layout_elements)

            # İşlem sonu temizlik
            if torch.cuda.is_available():
                try:
                    gc.collect()
                    torch.cuda.empty_cache()
                except:
                    pass

            return {
                'layout_elements': layout_elements,
                'ocr_lines': ocr_lines,
                'paragraphs': paragraphs,
                'statistics': {
                    'layout_count': len(layout_elements),
                    'ocr_lines': len(ocr_lines),
                    'matched_lines': sum(len(lines) for lines in element_to_lines.values()),
                    'paragraph_count': len(paragraphs),
                    'heading_count': len([p for p in paragraphs if p['type'] == 'heading']),
                    'original_size': original_size,
                    'processed_size': processed_image.size,
                    'layout_engine': self.layout_engine
                }
            }

        except RuntimeError as e:
            error_str = str(e).lower()
            if "out of memory" in error_str or "cuda" in error_str:
                print(f"   CUDA OOM hatasi! Bellek kurtariliyor...")

                try:
                    gc.collect()
                except:
                    pass

                try:
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except:
                    pass

                try:
                    if torch.cuda.is_available():
                        torch.cuda.synchronize()
                except:
                    pass

                raise
            else:
                raise

    def _surya_layout_analysis(self, image: Image.Image) -> List[Dict]:
        """
        Surya LayoutPredictor ile layout analizi - GPU Accelerated
        YOLO'ya alternatif olarak kullanılabilir.
        """
        if not self.surya_layout_available:
            print("   Surya Layout kullanilamiyor, YOLO'ya geciliyor")
            return self._yolo_layout_analysis(image)

        print("   Surya Layout analizi yapiliyor...")

        try:
            with torch.inference_mode():
                layout_results = self.layout_predictor([image])

            if not layout_results or len(layout_results) == 0:
                print("   Surya Layout sonucu bos")
                return []

            layout = layout_results[0]
            
            # image_bbox'tan referans boyut al
            actual_w, actual_h = image.size
            ref_w, ref_h = actual_w, actual_h
            
            if hasattr(layout, 'image_bbox') and layout.image_bbox:
                img_bbox = layout.image_bbox
                if len(img_bbox) >= 4:
                    ref_w = img_bbox[2] - img_bbox[0]
                    ref_h = img_bbox[3] - img_bbox[1]

            # Ölçeklendirme faktörü
            scale_w = actual_w / ref_w if ref_w > 0 else 1.0
            scale_h = actual_h / ref_h if ref_h > 0 else 1.0
            needs_scaling = abs(scale_w - 1.0) > 0.01 or abs(scale_h - 1.0) > 0.01

            elements = []
            
            if not hasattr(layout, 'bboxes') or not layout.bboxes:
                print("   Layout bboxes bulunamadi")
                return []

            for i, item in enumerate(layout.bboxes):
                # Label al
                label = getattr(item, 'label', 'Text') or 'Text'
                
                # Position al - KRITIK: Bu değer okuma sırası için kullanılacak
                position = getattr(item, 'position', i)
                
                # Confidence al
                confidence = 1.0
                if hasattr(item, 'top_k') and item.top_k:
                    confidence = max(item.top_k.values()) if item.top_k else 1.0

                # Polygon'dan bbox oluştur
                final_bbox = None
                
                if hasattr(item, 'polygon') and item.polygon:
                    poly = item.polygon
                    if poly and len(poly) >= 4:
                        x_coords = [p[0] for p in poly]
                        y_coords = [p[1] for p in poly]
                        
                        raw_bbox = [
                            min(x_coords),
                            min(y_coords),
                            max(x_coords),
                            max(y_coords)
                        ]
                        
                        if needs_scaling:
                            final_bbox = [
                                raw_bbox[0] * scale_w,
                                raw_bbox[1] * scale_h,
                                raw_bbox[2] * scale_w,
                                raw_bbox[3] * scale_h
                            ]
                        else:
                            final_bbox = raw_bbox

                # Fallback: bbox attribute
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

                if final_bbox is None:
                    continue

                # Sınır kontrolü
                final_bbox = [
                    max(0, min(final_bbox[0], actual_w)),
                    max(0, min(final_bbox[1], actual_h)),
                    max(0, min(final_bbox[2], actual_w)),
                    max(0, min(final_bbox[3], actual_h))
                ]

                elements.append({
                    'id': i + 1,
                    'bbox': final_bbox,
                    'label': label,
                    'confidence': confidence,
                    'position': position  # Surya'nın verdiği okuma sırası
                })

            print(f"   Surya Layout: {len(elements)} element tespit edildi")
            return elements

        except Exception as e:
            print(f"   Surya Layout hatasi: {e}")
            import traceback
            traceback.print_exc()
            # Fallback to YOLO
            print("   YOLO'ya geciliyor...")
            return self._yolo_layout_analysis(image)

    def _yolo_layout_analysis(self, image: Image.Image) -> List[Dict]:
        """YOLO ile layout analizi - GPU Accelerated"""
        if not self.yolo_available:
            print("   YOLO kullanilamiyor")
            return []

        print("   YOLO Layout analizi yapiliyor...")

        # GPU prediction
        results = self.yolo_model.predict(image, verbose=False)
        boxes = results[0].boxes
        names = self.yolo_model.model.names

        elements = []
        for i, box in enumerate(boxes):
            cls_id = int(box.cls)
            cls_name = names[cls_id]
            conf = float(box.conf)

            # Düşük güvenli filtreleme
            if conf < 0.35:
                continue

            xyxy = box.xyxy[0].tolist()

            elements.append({
                'id': i + 1,
                'bbox': xyxy,
                'label': cls_name,
                'confidence': conf,
                'position': i  # YOLO için varsayılan sıra (kolon mantığı ile override edilecek)
            })

        print(f"   YOLO Layout: {len(elements)} element tespit edildi")
        return elements

    def _surya_ocr_safe(self, image: Image.Image) -> List[Dict]:
        """SuryaOCR - OOM korumalı"""
        import gc

        try:
            # Önce detection
            with torch.inference_mode():
                det_results = self.detector([image])

            if not det_results or len(det_results) == 0:
                return []

            det_result = det_results[0]

            # Sonra recognition
            with torch.inference_mode():
                rec_results = self.recognizer([image], det_predictor=self.detector)

            if not rec_results or len(rec_results) == 0:
                return []

            rec_result = rec_results[0]

            # Satırları işle
            lines = []
            if hasattr(rec_result, 'text_lines'):
                for i, line in enumerate(rec_result.text_lines):
                    text = getattr(line, 'text', '') or ''
                    if not text.strip():
                        continue

                    # Polygon'dan bbox
                    bbox = None
                    if hasattr(line, 'polygon') and line.polygon:
                        poly = line.polygon
                        x_coords = [p[0] for p in poly]
                        y_coords = [p[1] for p in poly]
                        bbox = [min(x_coords), min(y_coords), max(x_coords), max(y_coords)]
                    elif hasattr(line, 'bbox') and line.bbox:
                        bbox = list(line.bbox)

                    if bbox:
                        lines.append({
                            'id': i + 1,
                            'text': text,
                            'bbox': bbox,
                            'confidence': getattr(line, 'confidence', 1.0)
                        })

            print(f"   OCR: {len(lines)} satir")
            return lines

        except RuntimeError as e:
            if "out of memory" in str(e).lower():
                print(f"   OCR OOM hatasi!")
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                raise
            raise
        except Exception as e:
            print(f"   OCR hatasi: {e}")
            return []

    def _remove_duplicate_lines(self, ocr_lines: List[Dict]) -> List[Dict]:
        """Yinelenen OCR satırlarını temizle"""
        if not ocr_lines:
            return []

        ocr_lines.sort(key=lambda x: (x['bbox'][1], x['bbox'][0]))

        cleaned = []

        for line in ocr_lines:
            y_center = (line['bbox'][1] + line['bbox'][3]) / 2
            x_center = (line['bbox'][0] + line['bbox'][2]) / 2

            is_duplicate = False

            for existing in cleaned[-5:]:
                existing_y = (existing['bbox'][1] + existing['bbox'][3]) / 2
                existing_x = (existing['bbox'][0] + existing['bbox'][2]) / 2

                if abs(y_center - existing_y) < 15 and abs(x_center - existing_x) < 50:
                    if self._text_similarity(line['text'], existing['text']) > 0.7:
                        is_duplicate = True
                        break

            if not is_duplicate:
                cleaned.append(line)

        return cleaned

    def _text_similarity(self, text1: str, text2: str) -> float:
        """İki metin arasındaki benzerlik oranı (0-1)"""
        if not text1 or not text2:
            return 0.0

        t1 = text1.lower().strip()
        t2 = text2.lower().strip()

        if t1 == t2:
            return 1.0

        if t1 in t2 or t2 in t1:
            return 0.9

        set1 = set(t1)
        set2 = set(t2)

        intersection = len(set1 & set2)
        union = len(set1 | set2)

        return intersection / union if union > 0 else 0.0

    def _match_ocr_to_layout(self, ocr_lines: List[Dict], layout_elements: List[Dict]) -> Dict[int, List[Dict]]:
        """OCR satırlarını layout elementleriyle eşleştir"""

        def calculate_overlap(bbox1, bbox2):
            if not bbox1 or not bbox2:
                return 0
            x1_min, y1_min, x1_max, y1_max = bbox1[:4]
            x2_min, y2_min, x2_max, y2_max = bbox2[:4]
            x_overlap = max(0, min(x1_max, x2_max) - max(x1_min, x2_min))
            y_overlap = max(0, min(y1_max, y2_max) - max(y1_min, y2_min))
            intersection = x_overlap * y_overlap
            area1 = (x1_max - x1_min) * (y1_max - y1_min)
            return intersection / area1 if area1 > 0 else 0

        def point_in_bbox(x, y, bbox):
            return bbox[0] <= x <= bbox[2] and bbox[1] <= y <= bbox[3]

        element_to_lines = {}

        for ocr_line in ocr_lines:
            line_bbox = ocr_line['bbox']
            line_center_x = (line_bbox[0] + line_bbox[2]) / 2
            line_center_y = (line_bbox[1] + line_bbox[3]) / 2

            best_match = None
            best_score = 0

            for element in layout_elements:
                elem_bbox = element['bbox']
                score = 0

                if point_in_bbox(line_center_x, line_center_y, elem_bbox):
                    score += 0.5

                overlap = calculate_overlap(line_bbox, elem_bbox)
                score += overlap

                if score > best_score:
                    best_score = score
                    best_match = element

            if best_match and best_score > 0.05:
                elem_id = best_match['id']
                if elem_id not in element_to_lines:
                    element_to_lines[elem_id] = []
                element_to_lines[elem_id].append(ocr_line)

        matched = sum(len(lines) for lines in element_to_lines.values())
        print(f"   {matched}/{len(ocr_lines)} satir eslesti")
        return element_to_lines

    def _create_reading_order(self, layout_elements: List[Dict]) -> List[Dict]:
        """
        Okuma sırası oluştur
        
        SURYA: position attribute'una göre sıralama (Surya'nın kendi okuma sırası)
               Kolon mantığı DEVRE DISI - Surya zaten doğru sırayı veriyor
               
        YOLO:  Kolon bazlı sıralama (geleneksel gazete okuma düzeni)
        """
        if not layout_elements:
            return []

        # ================================================================
        # SURYA: Position-based sıralama (Kolon mantığı YOK)
        # ================================================================
        if hasattr(self, 'layout_engine') and self.layout_engine == "surya":
            print("   [SURYA] Position-based okuma sirasi kullaniliyor (kolon mantigi DEVRE DISI)")
            
            # Surya'nın verdiği 'position' değerine göre sırala
            # Bu değer görüntüdeki 0, 1, 2, 3... numaralarına karşılık geliyor
            sorted_elements = sorted(layout_elements, key=lambda x: x.get('position', x.get('id', 0)))
            
            # Debug: İlk 5 elementin sırasını göster
            for i, elem in enumerate(sorted_elements[:5]):
                pos = elem.get('position', 'N/A')
                label = elem.get('label', 'unknown')
                print(f"      [{i}] position={pos}, label={label}")
            
            if len(sorted_elements) > 5:
                print(f"      ... ve {len(sorted_elements) - 5} element daha")
            
            return sorted_elements

        # ================================================================
        # YOLO: Kolon bazlı sıralama (Geleneksel gazete düzeni)
        # ================================================================
        print("   [YOLO] Kolon bazli siralama yapiliyor...")
        
        x_positions = []
        for elem in layout_elements:
            bbox = elem['bbox']
            x_center = (bbox[0] + bbox[2]) / 2
            x_positions.append((elem['id'], x_center, bbox[1]))

        x_positions.sort(key=lambda x: x[1])

        columns = []
        if x_positions:
            current_column = [x_positions[0]]
            prev_x = x_positions[0][1]

            if len(x_positions) > 2:
                x_diffs = [x_positions[i + 1][1] - x_positions[i][1] for i in range(len(x_positions) - 1)]
                avg_gap = sum(x_diffs) / len(x_diffs)
                threshold = max(120, avg_gap * 2.5)
            else:
                threshold = 150

            for elem_id, x_pos, y_pos in x_positions[1:]:
                if x_pos - prev_x > threshold:
                    columns.append(current_column)
                    current_column = [(elem_id, x_pos, y_pos)]
                else:
                    current_column.append((elem_id, x_pos, y_pos))
                prev_x = x_pos

            if current_column:
                columns.append(current_column)

        print(f"   {len(columns)} kolon tespit edildi")

        reading_order = []
        for column in columns:
            col_elements = []
            for elem_id, x_pos, y_pos in column:
                elem = next((e for e in layout_elements if e['id'] == elem_id), None)
                if elem:
                    col_elements.append((y_pos, elem))

            col_elements.sort(key=lambda x: x[0])
            for y_pos, elem in col_elements:
                reading_order.append(elem)

        return reading_order

    def _create_paragraphs(self, reading_order: List[Dict], element_to_lines: Dict,
                           layout_elements: List[Dict]) -> List[Dict]:
        """Paragrafları oluştur"""

        all_widths = [e['bbox'][2] - e['bbox'][0] for e in layout_elements]
        max_width = max(all_widths) if all_widths else 1000

        paragraphs = []
        counter = 0

        for element in reading_order:
            elem_id = element['id']

            if elem_id not in element_to_lines:
                continue

            lines = element_to_lines[elem_id]
            if not lines:
                continue

            lines.sort(key=lambda x: x['id'])
            full_text = ' '.join([line['text'] for line in lines])

            full_text = re.sub(r'<[^>]+>', '', full_text)
            full_text = re.sub(r'\s+', ' ', full_text).strip()

            if not full_text:
                continue

            counter += 1

            is_heading = self._is_heading(element, full_text, max_width)

            paragraphs.append({
                'number': counter,
                'text': full_text,
                'type': 'heading' if is_heading else 'paragraph',
                'confidence': element['confidence']
            })

        heading_count = len([p for p in paragraphs if p['type'] == 'heading'])
        print(f"   {len(paragraphs)} paragraf ({heading_count} baslik)")
        return paragraphs

    def _is_heading(self, element: Dict, text: str, max_width: float) -> bool:
        """Başlık tespiti"""
        bbox = element['bbox']
        text_width = bbox[2] - bbox[0]
        width_ratio = text_width / max_width
        words = text.split()
        label = element.get('label', '').lower()

        if width_ratio > 0.8 and 5 <= len(words) <= 30:
            return True

        if 'title' in label or 'header' in label or 'heading' in label or 'section' in label:
            return True

        if 1 <= len(words) <= 8 and text.isupper():
            return True

        return False