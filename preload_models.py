#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys

# Proje dizinini (module level) sys.path'e ekle
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.append(project_root)

# Kullanilacak modelleri ve dilleri dogrudan burada tanimlayalim
DETECTION_LANGS = ["tr", "en"]
RECOGNITION_LANGS = ["tr", "en"]

print("Modelleri on-yukleme baslatiliyor...")

try:
    # 1. SuryaOCR Detection Predictor (v0.17.0 API)
    print("[1/3] Detection Predictor yukleniyor...")
    from surya.detection import DetectionPredictor
    detection_predictor = DetectionPredictor()
    print("[1/3] Detection Predictor hazir.")

    # 2. SuryaOCR Recognition Predictor (v0.17.0 API)
    print("[2/3] Recognition Predictor yukleniyor...")
    from surya.foundation import FoundationPredictor
    from surya.recognition import RecognitionPredictor
    foundation_predictor = FoundationPredictor()
    recognition_predictor = RecognitionPredictor(foundation_predictor)
    print("[2/3] Recognition Predictor hazir.")

    # 3. DocLayout-YOLO Modeli (eger kullaniliyorsa)
    print("\n[3/3] DocLayout-YOLO Modeli indiriliyor/kontrol ediliyor...")
    try:
        from huggingface_hub import hf_hub_download
        hf_hub_download(
            repo_id="juliozhao/DocLayout-YOLO-DocStructBench", 
            filename="doclayout_yolo_docstructbench_imgsz1024.pt"
        )
        print("[3/3] DocLayout-YOLO hazir.")
    except Exception as e:
        print(f"[3/3] DocLayout-YOLO uyarisi: {e}")

    print("\nTum modeller basariyla on-bellege alindi.")

except Exception as e:
    print(f"\nModel indirme hatasi: {e}")
    sys.exit(1)